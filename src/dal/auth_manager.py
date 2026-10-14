"""Database-backed authentication and user provisioning."""

from __future__ import annotations

import hashlib
import hmac
import secrets

from src.db_manager import DatabaseManager

_HASH_ITERATIONS = 310_000
_SALT_BYTES = 16
_ROLE_BY_DEPARTMENT = {
    "human resources": "Admin",
    "sales": "Viewer",
    "research & development": "Viewer",
}


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
            SELECT u.username, u.password_hash, u.password_salt, u.role,
                   e.employee_id, d.department_name
            FROM users u
            LEFT JOIN employees e ON LOWER(TRIM(e.email)) = LOWER(TRIM(u.username))
            LEFT JOIN departments d ON d.department_id = e.department_id
            WHERE u.username = :username AND u.is_active = TRUE
            """,
            {"username": username.strip()},
        )
        if user and verify_password(
            password, user["password_hash"], user["password_salt"]
        ):
            if user["employee_id"] is not None:
                department = user["department_name"].strip().casefold()
                return _ROLE_BY_DEPARTMENT.get(department)
            return user["role"]
        return None

    def create_user(self, username: str, password: str, role: str) -> None:
        if role not in {"Admin", "Viewer"}:
            raise ValueError("Role must be Admin or Viewer.")
        username = username.strip()
        if not username or not password:
            raise ValueError("Username and password are required.")

        self._insert_user(username, password, role)

    def register_employee(self, email: str, password: str) -> str:
        """Create an employee account with a role derived from their department."""
        username = email.strip().casefold()
        if not username or not password:
            raise ValueError("Work email and password are required.")
        if len(password) < 8:
            raise ValueError("Password must be at least 8 characters long.")

        with self.database.transaction(self.database.SILVER) as conn:
            employee = self.database.read_one(
                self.database.SILVER,
                """
                SELECT d.department_name
                FROM employees e
                JOIN departments d ON d.department_id = e.department_id
                WHERE LOWER(TRIM(e.email)) = :email
                """,
                {"email": username},
                conn=conn,
            )
            if employee is None:
                raise ValueError("That work email is not associated with a StaffSync employee.")

            department = employee["department_name"].strip().casefold()
            role = _ROLE_BY_DEPARTMENT.get(department)
            if role is None:
                raise ValueError("Your department is not eligible for StaffSync access.")

            self._insert_user(username, password, role, conn=conn)

        return role

    def _insert_user(self, username: str, password: str, role: str, conn=None) -> None:
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
            conn=conn,
        )
