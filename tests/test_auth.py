from contextlib import nullcontext
import unittest
from unittest.mock import patch

from src.utils import auth


class TestAuth(unittest.TestCase):
    def test_authenticate_returns_configured_role(self):
        with patch(
            "src.utils.auth.AuthManager.authenticate",
            return_value="Admin",
        ) as authenticate:
            self.assertEqual(auth.authenticate("hr-admin", "secret"), "Admin")
        authenticate.assert_called_once_with("hr-admin", "secret")

    def test_authenticate_rejects_unknown_or_invalid_credentials(self):
        with patch("src.utils.auth.AuthManager.authenticate", return_value=None):
            self.assertIsNone(auth.authenticate("unknown", "secret"))

    def test_login_and_logout_manage_session_state(self):
        with patch.object(auth.st, "session_state", {}) as session_state:
            auth.log_in("alice", "Viewer")
            self.assertTrue(session_state[auth.SESSION_AUTHENTICATED])
            self.assertEqual(auth.current_username(), "alice")
            self.assertEqual(auth.current_role(), "Viewer")

            auth.log_out()
            self.assertFalse(auth.is_authenticated())
            self.assertIsNone(auth.current_role())

    def test_render_login_registers_and_signs_in_employee(self):
        with (
            patch.object(auth.st, "tabs", return_value=(nullcontext(), nullcontext())),
            patch.object(
                auth.st, "form", side_effect=[nullcontext(), nullcontext()]
            ),
            patch.object(
                auth.st,
                "text_input",
                side_effect=["", "", " HR@example.com ", "safe-passphrase", "safe-passphrase"],
            ),
            patch.object(auth.st, "form_submit_button", side_effect=[False, True]),
            patch.object(auth.st, "title"),
            patch.object(auth.st, "write"),
            patch.object(auth.st, "caption"),
            patch.object(auth.st, "success") as success,
            patch.object(auth.st, "rerun") as rerun,
            patch.object(auth, "register_employee", return_value="Admin") as register,
            patch.object(auth, "log_in") as log_in,
        ):
            auth.render_login()

        register.assert_called_once_with(" HR@example.com ", "safe-passphrase")
        log_in.assert_called_once_with("hr@example.com", "Admin")
        success.assert_called_once_with("Account created. You are signed in with Admin access.")
        rerun.assert_called_once_with()


if __name__ == "__main__":
    unittest.main()
