import unittest
from unittest.mock import patch

import pandas as pd

from src.dal.analytics_manager import AnalyticsManager


class TestAnalyticsManager(unittest.TestCase):
    def setUp(self):
        self.manager = AnalyticsManager()

    def test_get_kpis_calculates_metrics_and_zero_safe_attrition(self):
        rows = [
            {"total": 10, "left_company": 2},
            {
                "total": 4,
                "avg_score": 80.456,
                "avg_rating": 3.456,
                "avg_job_sat": 2.345,
                "avg_wlb": None,
            },
            {"total": 3, "budget": 1250.5},
            {"total": 1},
        ]
        with patch.object(self.manager, "read_one", side_effect=rows):
            metrics = self.manager.get_kpis()

        self.assertEqual(metrics, {
            "total_employees": 10,
            "attrition_rate_pct": 20.0,
            "total_reviews": 4,
            "avg_review_score": 80.46,
            "avg_performance_rating": 3.46,
            "avg_job_satisfaction": 2.35,
            "avg_work_life_balance": 0,
            "total_projects": 3,
            "total_project_budget": 1250.5,
            "overallocated_employees": 1,
        })

        with patch.object(self.manager, "read_one", side_effect=[
            {"total": 0, "left_company": 0},
            {"total": 0, "avg_score": None, "avg_rating": None, "avg_job_sat": None, "avg_wlb": None},
            {"total": 0, "budget": 0},
            {"total": 0},
        ]):
            empty_metrics = self.manager.get_kpis()
        self.assertEqual(empty_metrics["attrition_rate_pct"], 0)
        self.assertEqual(empty_metrics["avg_review_score"], 0)

    def test_dropdown_and_yearly_read_methods(self):
        with patch.object(self.manager, "read", return_value=pd.DataFrame({"year_number": [2025, 2024]})) as read:
            self.assertEqual(self.manager.get_years(), [2025, 2024])
            read.assert_called_once()

        with patch.object(self.manager, "read", return_value=pd.DataFrame({"department_name": ["A"]})):
            self.assertEqual(self.manager.get_department_names(), ["A"])

        methods_and_args = [
            ("yoy_performance", ("Sales",), {"dept": "Sales"}),
            ("yoy_performance", (), {"dept": None}),
            ("yoy_overall", (), None),
            ("top_employees", (2025, "Sales", "5"), {"n": 5, "yr": 2025, "dept": "Sales"}),
            ("top_employees", (), {"n": 10, "yr": None, "dept": None}),
            ("attrition_by_department", (), None),
            ("attrition_risk", ("7",), {"n": 7}),
            ("attrition_risk", (), {"n": 25}),
            ("project_status_counts", (), None),
            ("employee_history", (9,), {"id": 9}),
        ]
        for method_name, args, expected_params in methods_and_args:
            with self.subTest(method=method_name, args=args), patch.object(
                self.manager, "read", return_value="result"
            ) as read:
                self.assertEqual(getattr(self.manager, method_name)(*args), "result")
                self.assertEqual(read.call_args.args[0], self.manager.GOLD)
                if expected_params is not None:
                    self.assertEqual(read.call_args.args[2], expected_params)
                else:
                    self.assertEqual(len(read.call_args.args), 2)

    def test_project_bottlenecks_handles_empty_and_sets_each_flag(self):
        empty = pd.DataFrame()
        with patch.object(self.manager, "read", return_value=empty):
            self.assertIs(self.manager.project_bottlenecks(), empty)

        frame = pd.DataFrame({
            "project_id": [1, 2, 3, 4, 5, 6],
            "assigned_employee_count": [1, 1, 1, 1, 1, 0],
            "total_allocation_pct": [100, 98, 90, 40, 30, 0],
            "average_review_score": [10, 100, 50, 40, 80, 80],
        })
        with patch.object(self.manager, "read", return_value=frame):
            result = self.manager.project_bottlenecks().set_index("project_id")

        self.assertEqual(result.loc[1, "flag"], "Critical")
        self.assertEqual(result.loc[2, "flag"], "Busy")
        self.assertEqual(result.loc[4, "flag"], "Low scores")
        self.assertEqual(result.loc[3, "flag"], "OK")
        self.assertTrue(pd.isna(result.loc[6, "avg_allocation_pct"]))

    def test_refresh_warehouse_success_and_failure(self):
        with patch.object(self.manager, "execute_procedure") as execute:
            self.assertEqual(self.manager.refresh_warehouse(), (True, "Warehouse refreshed."))
        execute.assert_called_once_with(self.manager.GOLD, "sp_populate_olap")

        with patch.object(self.manager, "execute_procedure", side_effect=RuntimeError("offline")):
            self.assertEqual(self.manager.refresh_warehouse(), (False, "Refresh failed: offline"))


if __name__ == "__main__":
    unittest.main()
