import unittest
from contextlib import nullcontext
from unittest.mock import Mock, patch

from src.dal.auth_manager import AuthManager


class TestAuthManager(unittest.TestCase):
    def setUp(self):
        self.database = Mock()
        self.database.SILVER = "silver"
        self.connection = object()
        self.database.transaction.return_value = nullcontext(self.connection)
        self.manager = AuthManager(self.database)

    def test_authenticate_uses_current_employee_department_role(self):
        self.database.read_one.return_value = {
            "username": "person@example.com",
            "password_hash": "hash",
            "password_salt": "salt",
            "role": "Admin",
            "employee_id": 42,
            "department_name": "Sales",
        }

        with patch("src.auth_manager.verify_password", return_value=True):
            role = self.manager.authenticate("person@example.com", "password")

        self.assertEqual(role, "Viewer")

    def test_authenticate_uses_stored_role_for_manually_provisioned_user(self):
        self.database.read_one.return_value = {
            "username": "hr-admin",
            "password_hash": "hash",
            "password_salt": "salt",
            "role": "Admin",
            "employee_id": None,
            "department_name": None,
        }

        with patch("src.auth_manager.verify_password", return_value=True):
            role = self.manager.authenticate("hr-admin", "password")

        self.assertEqual(role, "Admin")

    def test_register_employee_assigns_role_from_department(self):
        cases = (
            ("Human Resources", "Admin"),
            ("Sales", "Viewer"),
            ("Research & Development", "Viewer"),
        )

        for department, expected_role in cases:
            with self.subTest(department=department):
                self.database.reset_mock()
                self.database.SILVER = "silver"
                self.database.transaction.return_value = nullcontext(self.connection)
                self.database.read_one.return_value = {"department_name": department}
                with patch("src.auth_manager.hash_password", return_value=("hash", "salt")):
                    role = self.manager.register_employee(" Person@Example.com ", "safe-passphrase")

                self.assertEqual(role, expected_role)
                self.database.read_one.assert_called_once()
                self.assertEqual(
                    self.database.read_one.call_args.kwargs["conn"], self.connection
                )
                params = self.database.write.call_args.args[2]
                self.assertEqual(params["username"], "person@example.com")
                self.assertEqual(params["role"], expected_role)
                self.assertEqual(params["password_hash"], "hash")
                self.assertEqual(params["password_salt"], "salt")
                self.assertEqual(self.database.write.call_args.kwargs["conn"], self.connection)

    def test_register_employee_rejects_unknown_work_email(self):
        self.database.read_one.return_value = None

        with self.assertRaisesRegex(ValueError, "not associated with a StaffSync employee"):
            self.manager.register_employee("unknown@example.com", "safe-passphrase")

        self.database.write.assert_not_called()

    def test_register_employee_rejects_unmapped_department(self):
        self.database.read_one.return_value = {"department_name": "Finance"}

        with self.assertRaisesRegex(ValueError, "department is not eligible"):
            self.manager.register_employee("person@example.com", "safe-passphrase")

        self.database.write.assert_not_called()

    def test_register_employee_requires_eight_character_password(self):
        with self.assertRaisesRegex(ValueError, "at least 8 characters"):
            self.manager.register_employee("person@example.com", "short")

        self.database.transaction.assert_not_called()


if __name__ == "__main__":
    unittest.main()
