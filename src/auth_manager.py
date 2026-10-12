"""Database-backed authentication and user provisioning."""

from __future__ import annotations

import hashlib
import hmac
import secrets

from src.db_manager import DatabaseManager

_HASH_ITERATIONS = 310_000
_SALT_BYTES = 16


def hash_password(password: str, salt: bytes | None = None) -> tuple[str, str]:
    """Return a PBKDF2-HMAC-SHA256 password hash and hex salt."""
    salt = salt or secrets.token_bytes(_SALT_BYTES)
    password_hash = hashlib.pbkdf2_hmac(
        "sha256", password.encode("utf-8"), salt, _HASH_ITERATIONS
    )
    return password_hash.hex(), salt.hex()


def verify_password(password: str, password_hash: str, password_salt: str) -> bool:
    """Verify a password against its stored PBKDF2 hash and salt."""
    calculated_hash, _ = hash_password(password, bytes.fromhex(password_salt))
    return hmac.compare_digest(calculated_hash, password_hash)


class AuthManager:
    """Read and manage users in the configured Silver schema."""

    def __init__(self, database: DatabaseManager | None = None):
        self.database = database or DatabaseManager()

    def authenticate(self, username: str, password: str) -> str | None:
        user = self.database.read_one(
            self.database.SILVER,
            """
            SELECT username, password_hash, password_salt, role
            FROM users
            WHERE username = :username AND is_active = TRUE
            """,
            {"username": username.strip()},
        )
        if user and verify_password(
            password, user["password_hash"], user["password_salt"]
        ):
            return user["role"]
        return None

    def create_user(self, username: str, password: str, role: str) -> None:
        if role not in {"Admin", "Viewer"}:
            raise ValueError("Role must be Admin or Viewer.")
        if not username.strip() or not password:
            raise ValueError("Username and password are required.")

        password_hash, password_salt = hash_password(password)
        self.database.write(
            self.database.SILVER,
            """
            INSERT INTO users (username, password_hash, password_salt, role)
            VALUES (:username, :password_hash, :password_salt, :role)
            """,
            {
                "username": username.strip(),
                "password_hash": password_hash,
                "password_salt": password_salt,
                "role": role,
            },
        )
