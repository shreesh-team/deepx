import base64
import hashlib
import os


def hash_password(plain: str) -> str:
    salt = os.urandom(32)
    key = hashlib.pbkdf2_hmac("sha256", plain.encode(), salt, 260_000)
    return base64.b64encode(salt + key).decode()


def verify_password(plain: str, hashed: str) -> bool:
    data = base64.b64decode(hashed.encode())
    salt, stored_key = data[:32], data[32:]
    key = hashlib.pbkdf2_hmac("sha256", plain.encode(), salt, 260_000)
    return key == stored_key
