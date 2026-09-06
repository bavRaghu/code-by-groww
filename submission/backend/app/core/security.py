import base64
import hashlib
import hmac
import json
import secrets
import time
from typing import Any

from app.config import settings

def hash_password(password: str) -> str:
    """
    Hashes a password using memory-hard scrypt algorithm with a cryptographically
    secure 16-byte random salt.
    Format: scrypt$16384$8$1$<salt_b64>$<key_b64>
    """
    salt = secrets.token_bytes(16)
    key = hashlib.scrypt(password.encode("utf-8"), salt=salt, n=16384, r=8, p=1)
    salt_b64 = base64.b64encode(salt).decode("ascii")
    key_b64 = base64.b64encode(key).decode("ascii")
    return f"scrypt$16384$8$1${salt_b64}${key_b64}"

def verify_password(plain_password: str, hashed_password: str) -> bool:
    """
    Verifies a plain password against an scrypt hash in constant time
    to prevent timing side-channel attacks.
    """
    try:
        parts = hashed_password.split("$")
        if len(parts) != 6 or parts[0] != "scrypt":
            return False
        n = int(parts[1])
        r = int(parts[2])
        p = int(parts[3])
        salt = base64.b64decode(parts[4].encode("ascii"))
        expected_key = base64.b64decode(parts[5].encode("ascii"))
        derived_key = hashlib.scrypt(plain_password.encode("utf-8"), salt=salt, n=n, r=r, p=p)
        return secrets.compare_digest(derived_key, expected_key)
    except Exception:
        return False

def _b64url_encode(data: bytes) -> str:
    return base64.urlsafe_b64encode(data).decode("ascii").rstrip("=")

def _b64url_decode(s: str) -> bytes:
    pad = 4 - (len(s) % 4) if len(s) % 4 else 0
    return base64.urlsafe_b64decode((s + "=" * pad).encode("ascii"))

def create_access_token(user_id: int, email: str, expires_delta_seconds: int | None = None) -> str:
    """
    Creates an RFC 7519 compliant HS256 signed JSON Web Token (JWT).
    """
    if expires_delta_seconds is None:
        expires_delta_seconds = settings.access_token_expire_minutes * 60

    now = int(time.time())
    header = {"alg": "HS256", "typ": "JWT"}
    payload = {
        "sub": str(user_id),
        "email": email,
        "iat": now,
        "exp": now + expires_delta_seconds,
    }

    h_str = _b64url_encode(json.dumps(header, separators=(",", ":")).encode("utf-8"))
    p_str = _b64url_encode(json.dumps(payload, separators=(",", ":")).encode("utf-8"))
    signing_input = f"{h_str}.{p_str}".encode("ascii")
    sig = hmac.new(settings.secret_key.encode("utf-8"), signing_input, hashlib.sha256).digest()
    s_str = _b64url_encode(sig)
    return f"{h_str}.{p_str}.{s_str}"

def decode_access_token(token: str) -> dict[str, Any] | None:
    """
    Verifies and decodes an HS256 JWT. Returns payload dict if valid and unexpired, None otherwise.
    """
    try:
        parts = token.split(".")
        if len(parts) != 3:
            return None
        h_str, p_str, s_str = parts
        signing_input = f"{h_str}.{p_str}".encode("ascii")
        expected_sig = hmac.new(settings.secret_key.encode("utf-8"), signing_input, hashlib.sha256).digest()
        actual_sig = _b64url_decode(s_str)
        if not secrets.compare_digest(actual_sig, expected_sig):
            return None

        payload_bytes = _b64url_decode(p_str)
        payload = json.loads(payload_bytes.decode("utf-8"))
        exp = payload.get("exp")
        if exp is None or exp < time.time():
            return None
        return payload
    except Exception:
        return None
