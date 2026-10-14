"""Create a database-backed StaffSync login user."""

from getpass import getpass
from pathlib import Path
import sys

# Make the repository package importable when this file is run directly.
PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from src.dal.auth_manager import AuthManager


def main() -> int:
    if len(sys.argv) != 3 or sys.argv[2] not in {"Admin", "Viewer"}:
        print("Usage: python scripts/create_user.py <username> <Admin|Viewer>")
        return 2

    username, role = sys.argv[1:]
    password = getpass("Password: ")
    if password != getpass("Confirm password: "):
        print("Passwords do not match.")
        return 1

    AuthManager().create_user(username, password, role)
    print(f"Created {role} user '{username}'.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
