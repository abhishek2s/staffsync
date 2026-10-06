import unittest
from contextlib import nullcontext
from unittest.mock import Mock, patch

from config.settings import settings
from src.db_manager import DatabaseConnection, DatabaseManager
from src.utils.logger import setup_logger


class TestDatabaseManager(unittest.TestCase):
    def setUp(self):
        self.manager = DatabaseManager()
        self.saved_engines = DatabaseManager._engines.copy()
        DatabaseManager._engines.clear()

    def tearDown(self):
        DatabaseManager._engines.clear()
        DatabaseManager._engines.update(self.saved_engines)

    def test_alias_and_singleton(self):
        self.assertIs(DatabaseConnection, DatabaseManager)
        self.assertIs(self.manager, DatabaseManager())

    def test_logger_reuses_existing_logger_handlers(self):
        logger = setup_logger("DatabaseManager")
        self.assertIs(logger, setup_logger("DatabaseManager"))

    def test_get_engine_builds_encoded_url_and_caches_engine(self):
        expected_engine = object()
        with (
            patch.object(settings.DB, "USER", "user name"),
            patch.object(settings.DB, "PASSWORD", "p@ss word"),
            patch.object(settings.DB, "HOST", "db.example"),
            patch.object(settings.DB, "PORT", 1234),
            patch("src.db_manager.create_engine", return_value=expected_engine) as create_engine,
        ):
            first = self.manager.get_engine("schema")
            second = self.manager.get_engine("schema")

        self.assertIs(first, expected_engine)
        self.assertIs(second, expected_engine)
        create_engine.assert_called_once_with(
            "mysql+pymysql://user+name:p%40ss+word@db.example:1234/schema",
            pool_pre_ping=True,
            pool_size=10,
            max_overflow=20,
        )

    def test_connection_yields_and_closes_engine_connection(self):
        conn = object()
        engine = Mock()
        engine.connect.return_value = nullcontext(conn)
        with patch.object(self.manager, "get_engine", return_value=engine):
            with self.manager.connection("silver") as borrowed:
                self.assertIs(borrowed, conn)
        engine.connect.assert_called_once_with()

    def test_transaction_disables_primary_key_requirement(self):
        conn = Mock()
        engine = Mock()
        engine.begin.return_value = nullcontext(conn)
        with patch.object(self.manager, "get_engine", return_value=engine):
            with self.manager.transaction("silver") as borrowed:
                self.assertIs(borrowed, conn)
        conn.execute.assert_called_once()
        self.assertIn("sql_require_primary_key", str(conn.execute.call_args.args[0]))

    def test_transaction_skips_primary_key_statement_when_disabled(self):
        conn = Mock()
        engine = Mock()
        engine.begin.return_value = nullcontext(conn)
        with (
            patch.object(self.manager, "RELAX_PRIMARY_KEY_RULE", False),
            patch.object(self.manager, "get_engine", return_value=engine),
        ):
            with self.manager.transaction("silver") as borrowed:
                self.assertIs(borrowed, conn)
        conn.execute.assert_not_called()

    def test_operation_logs_success_and_reraises_errors(self):
        with patch("src.db_manager.logger") as logger:
            with self.manager.operation("read data"):
                pass
            logger.info.assert_any_call("read data - started")
            self.assertTrue(logger.info.call_args.args[0].startswith("read data - done in "))

            with self.assertRaisesRegex(ValueError, "bad operation"):
                with self.manager.operation("write data"):
                    raise ValueError("bad operation")
            logger.error.assert_called_once()
            self.assertIn("write data - FAILED after ", logger.error.call_args.args[0])

    def test_read_uses_provided_connection_and_empty_params(self):
        conn = object()
        frame = object()
        with patch("src.db_manager.pd.read_sql", return_value=frame) as read_sql:
            result = self.manager.read("silver", "SELECT 1", conn=conn)
        self.assertIs(result, frame)
        self.assertIs(read_sql.call_args.args[1], conn)
        self.assertEqual(read_sql.call_args.kwargs["params"], {})

    def test_read_opens_connection_when_none_is_provided(self):
        conn = object()
        engine = Mock()
        engine.connect.return_value = nullcontext(conn)
        with (
            patch.object(self.manager, "get_engine", return_value=engine),
            patch("src.db_manager.pd.read_sql", return_value="frame") as read_sql,
        ):
            result = self.manager.read("silver", "SELECT :value", {"value": 3})
        self.assertEqual(result, "frame")
        self.assertIs(read_sql.call_args.args[1], conn)
        self.assertEqual(read_sql.call_args.kwargs["params"], {"value": 3})

    def test_read_one_maps_row_or_returns_none_with_given_connection(self):
        conn = Mock()
        conn.execute.return_value.mappings.return_value.first.return_value = {"id": 1}
        self.assertEqual(self.manager.read_one("silver", "SELECT 1", conn=conn), {"id": 1})
        conn.execute.return_value.mappings.return_value.first.return_value = None
        self.assertIsNone(self.manager.read_one("silver", "SELECT 1", conn=conn))

    def test_read_one_opens_connection_when_none_is_provided(self):
        conn = Mock()
        conn.execute.return_value.mappings.return_value.first.return_value = {"id": 2}
        engine = Mock()
        engine.connect.return_value = nullcontext(conn)
        with patch.object(self.manager, "get_engine", return_value=engine):
            self.assertEqual(self.manager.read_one("silver", "SELECT 1", {"x": 2}), {"id": 2})
        self.assertEqual(conn.execute.call_args.args[1], {"x": 2})

    def test_write_uses_given_connection(self):
        conn = Mock()
        conn.execute.return_value.rowcount = 4
        self.assertEqual(self.manager.write("silver", "UPDATE t", conn=conn), 4)
        self.assertEqual(conn.execute.call_args.args[1], {})

    def test_write_creates_transaction_when_no_connection_is_given(self):
        conn = Mock()
        conn.execute.return_value.rowcount = 1
        with patch.object(self.manager, "transaction", return_value=nullcontext(conn)) as transaction:
            self.assertEqual(self.manager.write("silver", "INSERT", {"x": 1}), 1)
        transaction.assert_called_once_with("silver")
        self.assertEqual(conn.execute.call_args.args[1], {"x": 1})

    def test_execute_procedure_runs_inside_transaction(self):
        conn = Mock()
        with (
            patch.object(self.manager, "operation", return_value=nullcontext()),
            patch.object(self.manager, "transaction", return_value=nullcontext(conn)) as transaction,
        ):
            self.manager.execute_procedure("gold", "refresh_data")

        transaction.assert_called_once_with("gold")
        self.assertIn("CALL refresh_data();", str(conn.execute.call_args.args[0]))


if __name__ == "__main__":
    unittest.main()
