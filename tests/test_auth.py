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


if __name__ == "__main__":
    unittest.main()
