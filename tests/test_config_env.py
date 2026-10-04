import unittest

from config.settings import settings
from src.db_manager import DatabaseManager


class TestEnvironmentConfiguration(unittest.TestCase):
    def test_database_settings_are_loaded_from_project_env(self):
        self.assertEqual(settings.DB.HOST, "localhost")
        self.assertEqual(settings.DB.USER, "root")
        self.assertEqual(settings.DB.PASSWORD, "MySQL@123")

    def test_database_manager_uses_configured_credentials(self):
        manager = DatabaseManager()
        self.assertEqual(manager.SILVER, settings.DB.SILVER_SCHEMA)
        self.assertEqual(manager.GOLD, settings.DB.GOLD_SCHEMA)
        self.assertIs(manager, DatabaseManager())


if __name__ == "__main__":
    unittest.main()
