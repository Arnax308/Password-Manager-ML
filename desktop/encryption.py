import os
import secrets
from cryptography.hazmat.primitives.ciphers.aead import AESGCM
from cryptography.hazmat.primitives.kdf.pbkdf2 import PBKDF2HMAC
from cryptography.hazmat.primitives import hashes
import base64

def generate_salt():
    return secrets.token_bytes(16)

def derive_key(password: str, salt: bytes) -> bytes:
    kdf = PBKDF2HMAC(
        algorithm=hashes.SHA256(),
        length=32,
        salt=salt,
        iterations=480000,
    )
    return kdf.derive(password.encode('utf-8'))

def verify_master_password(password: str, salt: bytes, test_ciphertext: bytes, nonce: bytes) -> bool:
    try:
        key = derive_key(password, salt)
        aesgcm = AESGCM(key)
        aesgcm.decrypt(nonce, test_ciphertext, None)
        return True
    except Exception:
        return False

def encrypt_data(data: str, key: bytes) -> tuple[bytes, bytes]:
    aesgcm = AESGCM(key)
    nonce = secrets.token_bytes(12)
    ciphertext = aesgcm.encrypt(nonce, data.encode('utf-8'), None)
    return ciphertext, nonce

def decrypt_data(ciphertext: bytes, nonce: bytes, key: bytes) -> str:
    aesgcm = AESGCM(key)
    plaintext = aesgcm.decrypt(nonce, ciphertext, None)
    return plaintext.decode('utf-8')

def setup_vault_keys(password: str) -> tuple[bytes, bytes, bytes]:
    """Generates a salt, derives the key, and creates a test encryption to verify the password later."""
    salt = generate_salt()
    key = derive_key(password, salt)
    
    # Encrypt a known string (e.g., 'VAULT_VALID') to verify master password later
    test_cipher, test_nonce = encrypt_data("VAULT_VALID", key)
    return salt, test_cipher, test_nonce

