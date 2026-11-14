"""Password hashing and opaque server sessions; no bearer token in localStorage."""
import hashlib
import hmac
import secrets
from datetime import datetime, timedelta, timezone

def digest_password(password: str) -> str:
    salt = secrets.token_bytes(16)
    digest = hashlib.scrypt(password.encode(), salt=salt, n=2**14, r=8, p=1)
    return "scrypt$" + salt.hex() + "$" + digest.hex()

def check_password(password: str, stored: str) -> bool:
    try:
        name, salt_hex, expected = stored.split("$")
        if name != "scrypt":
            return False
        actual = hashlib.scrypt(password.encode(), salt=bytes.fromhex(salt_hex), n=2**14, r=8, p=1)
        return hmac.compare_digest(actual, bytes.fromhex(expected))
    except (ValueError, TypeError):
        return False

def session_pair():
    token = secrets.token_urlsafe(40)
    return token, hashlib.sha256(token.encode()).hexdigest(), secrets.token_urlsafe(32), datetime.now(timezone.utc) + timedelta(days=7)

def token_hash(token: str) -> str:
    return hashlib.sha256(token.encode()).hexdigest()
