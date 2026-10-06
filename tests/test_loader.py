import tempfile
import unittest
from contextlib import nullcontext
from pathlib import Path
from unittest.mock import Mock, patch

import pandas as pd
from sqlalchemy.exc import SQLAlchemyError

from src.loader import BronzeLoader, DATE_COLUMNS


class TestBronzeLoader(unittest.TestCase):
    def setUp(self):
        self.loader = BronzeLoader()

    def test_engine_uses_encoded_credentials(self):
        with patch("src.loader.create_engine", return_value="engine") as create_engine:
            result = self.loader._engine()
        self.assertEqual(result, "engine")
        create_engine.assert_called_once()
        self.assertIn("mysql+pymysql://", create_engine.call_args.args[0])
        self.assertTrue(create_engine.call_args.kwargs["pool_pre_ping"])

    def test_truncate_table_executes_quoted_table_name(self):
        conn = Mock()
        engine = Mock()
        engine.begin.return_value = nullcontext(conn)
        self.loader.truncate_table(engine, "stg_employee")
        conn.execute.assert_called_once()
        self.assertIn("TRUNCATE TABLE `stg_employee`", str(conn.execute.call_args.args[0]))

    def test_load_table_raises_for_missing_csv(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            self.loader.data_dir = Path(temp_dir)
            with self.assertRaisesRegex(FileNotFoundError, "stg_employee.csv not found"):
                self.loader.load_table(Mock(), "stg_employee")

    def test_load_table_truncates_and_counts_chunks(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            self.loader.data_dir = Path(temp_dir)
            (self.loader.data_dir / "stg_employee.csv").touch()
            chunks = [pd.DataFrame({"id": [1, 2]}), pd.DataFrame({"id": [3]})]
            engine = Mock()
            with (
                patch.object(self.loader, "truncate_table") as truncate,
                patch("src.loader.pd.read_csv", return_value=iter(chunks)) as read_csv,
                patch.object(pd.DataFrame, "to_sql") as to_sql,
            ):
                self.assertEqual(self.loader.load_table(engine, "stg_employee"), 3)

        truncate.assert_called_once_with(engine, "stg_employee")
        read_csv.assert_called_once_with(
            self.loader.data_dir / "stg_employee.csv",
            parse_dates=DATE_COLUMNS["stg_employee"],
            chunksize=20_000,
        )
        self.assertEqual(to_sql.call_count, 2)
        self.assertEqual(to_sql.call_args.kwargs["method"], "multi")

    def test_load_table_logs_and_reraises_sqlalchemy_errors(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            self.loader.data_dir = Path(temp_dir)
            (self.loader.data_dir / "stg_review.csv").touch()
            with (
                patch.object(self.loader, "truncate_table"),
                patch("src.loader.pd.read_csv", side_effect=SQLAlchemyError("insert failed")),
                self.assertRaisesRegex(SQLAlchemyError, "insert failed"),
            ):
                self.loader.load_table(Mock(), "stg_review")

    def test_run_disables_primary_key_rule_then_loads_all_tables(self):
        conn = Mock()
        engine = Mock()
        engine.begin.return_value = nullcontext(conn)
        with (
            patch.object(self.loader, "_engine", return_value=engine),
            patch.object(self.loader, "load_table") as load_table,
        ):
            self.loader.run()

        self.assertIn("sql_require_primary_key", str(conn.execute.call_args.args[0]))
        self.assertEqual(
            [call.args[1] for call in load_table.call_args_list],
            list(DATE_COLUMNS),
        )


if __name__ == "__main__":
    unittest.main()
