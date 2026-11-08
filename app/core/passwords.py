import hashlib
import secrets


def hash_password(password):
    salt = secrets.token_bytes(16)
    digest = hashlib.scrypt(password.encode(), salt=salt, n=16384, r=8, p=1, dklen=32)
    return f"scrypt:{salt.hex()}:{digest.hex()}"


def verify_password(password, encoded):
    try:
        algorithm, salt, expected = encoded.split(":")
        if algorithm != "scrypt" or len(salt) != 32 or len(expected) != 64:
            return False
        actual = hashlib.scrypt(password.encode(), salt=bytes.fromhex(salt), n=16384, r=8, p=1, dklen=32)
        return secrets.compare_digest(actual.hex(), expected)
    except (ValueError, TypeError):
        return False
