import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

import pandas as pd

from src.synthesizer import DataSynthesizer, to_snake


def source_rows():
    return pd.DataFrame([
        {
            "Age": 35,
            "Attrition": "No",
            "Department": "A",
            "JobRole": "Engineer",
            "JobLevel": 2,
            "MonthlyIncome": 5000,
            "YearsAtCompany": 6,
            "PerformanceRating": 3,
            "Gender": "Male",
            "JobSatisfaction": 3,
            "WorkLifeBalance": 2,
            "EnvironmentSatisfaction": 4,
            "TotalWorkingYears": 10,
            "YearsInCurrentRole": 3,
            "YearsWithCurrManager": 3,
            "YearsSinceLastPromotion": 2,
            "HourlyRate": 50,
            "DailyRate": 600,
            "MonthlyRate": 15000,
            "EmployeeCount": 1,
            "EmployeeNumber": 1,
            "Over18": "Y",
            "StandardHours": 80,
            "EducationField": "Life Sciences",
        },
        {
            "Age": 30,
            "Attrition": "Yes",
            "Department": "B",
            "JobRole": "Analyst",
            "JobLevel": 1,
            "MonthlyIncome": 4000,
            "YearsAtCompany": 4,
            "PerformanceRating": 3,
            "Gender": "Female",
            "JobSatisfaction": 2,
            "WorkLifeBalance": 3,
            "EnvironmentSatisfaction": 3,
            "TotalWorkingYears": 8,
            "YearsInCurrentRole": 2,
            "YearsWithCurrManager": 2,
            "YearsSinceLastPromotion": 1,
            "HourlyRate": 40,
            "DailyRate": 500,
            "MonthlyRate": 12000,
            "EmployeeCount": 1,
            "EmployeeNumber": 2,
            "Over18": "Y",
            "StandardHours": 80,
            "EducationField": "Medical",
        },
    ])


class TestDataSynthesizer(unittest.TestCase):
    def test_to_snake_converts_pascal_case(self):
        self.assertEqual(to_snake("MonthlyIncome"), "monthly_income")
        self.assertEqual(to_snake("age"), "age")

    def write_source(self, path, frame=None):
        (frame if frame is not None else source_rows()).to_csv(path, index=False)

    def test_load_base_rejects_missing_file_and_missing_columns(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            missing_path = Path(temp_dir) / "missing.csv"
            with self.assertRaisesRegex(FileNotFoundError, "Download IBM HR dataset"):
                DataSynthesizer(source_csv=str(missing_path)).load_base()

            bad_path = Path(temp_dir) / "bad.csv"
            pd.DataFrame({"Age": [30]}).to_csv(bad_path, index=False)
            with self.assertRaisesRegex(ValueError, "Source CSV missing required columns"):
                DataSynthesizer(source_csv=str(bad_path)).load_base()

    def test_load_base_normalizes_columns_drops_unused_fields_and_builds_roles(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            path = Path(temp_dir) / "source.csv"
            self.write_source(path)
            synthesizer = DataSynthesizer(source_csv=str(path), target_rows=3)
            synthesizer.load_base()

        self.assertIn("monthly_income", synthesizer.base.columns)
        self.assertNotIn("employee_count", synthesizer.base.columns)
        self.assertEqual(synthesizer._dept_roles, {"A": ["Engineer"], "B": ["Analyst"]})

    def make_loaded_synthesizer(self, temp_dir, target_rows=3):
        path = Path(temp_dir) / "source.csv"
        self.write_source(path)
        synthesizer = DataSynthesizer(
            source_csv=str(path),
            out_dir=str(Path(temp_dir) / "out"),
            target_rows=target_rows,
            history_share=1,
            n_projects=8,
            seed=13,
        )
        synthesizer.load_base()
        return synthesizer

    def test_build_employees_creates_ids_names_dates_and_caps_extra_rows(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            synthesizer = self.make_loaded_synthesizer(temp_dir, target_rows=3)
            synthesizer.build_employees()
            employees = synthesizer.employees

        self.assertEqual(len(employees), 3)
        self.assertEqual(employees["employee_id"].tolist(), [1, 2, 3])
        self.assertTrue(employees["email"].str.endswith("@company.com").all())
        self.assertTrue((employees["hire_date"] == employees["effective_from"]).all())
        self.assertTrue((employees["years_at_company"] <= employees["total_working_years"]).all())

    def test_undo_change_handles_department_promotion_salary_and_level_one(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            synthesizer = self.make_loaded_synthesizer(temp_dir)
            current = {
                "department": "A",
                "job_role": "Engineer",
                "job_level": 2,
                "monthly_income": 5000,
            }

            synthesizer.rng = unittest.mock.Mock()
            synthesizer.rng.choice.side_effect = ["DEPARTMENT_CHANGE", "B", "Analyst"]
            previous, reason = synthesizer._undo_change(current, ["A", "B"])
            self.assertEqual(reason, "DEPARTMENT_CHANGE")
            self.assertEqual(previous["department"], "B")
            self.assertEqual(previous["job_role"], "Analyst")

            synthesizer.rng.choice.side_effect = None
            synthesizer.rng.choice.return_value = "PROMOTION"
            synthesizer.rng.uniform.return_value = 1.25
            previous, reason = synthesizer._undo_change(current, ["A", "B"])
            self.assertEqual(reason, "PROMOTION")
            self.assertEqual(previous["job_level"], 1)

            synthesizer.rng.uniform.return_value = 1.1
            previous, reason = synthesizer._undo_change({**current, "job_level": 1}, ["A", "B"])
            self.assertEqual(reason, "SALARY_HIKE")
            self.assertEqual(previous["job_level"], 1)

            synthesizer.rng.choice.return_value = "SALARY_HIKE"
            previous, reason = synthesizer._undo_change(current, ["A", "B"])
            self.assertEqual(reason, "SALARY_HIKE")
            self.assertLess(previous["monthly_income"], current["monthly_income"])

    def test_build_history_projects_assignments_reviews_and_noise(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            synthesizer = self.make_loaded_synthesizer(temp_dir)
            synthesizer.build_employees()
            synthesizer.build_history()
            self.assertEqual(len(synthesizer.history), 3)
            self.assertTrue((synthesizer.history["valid_to"] < pd.Timestamp("2025-12-31")).all())

            synthesizer.build_projects()
            self.assertEqual(len(synthesizer.projects), 8)
            self.assertTrue(set(synthesizer.projects["status"]).issubset({"Active", "Completed"}))

            synthesizer.projects = pd.DataFrame({
                "project_id": [1, 2],
                "department": ["A", "B"],
                "start_date": pd.to_datetime(["2019-01-01", "2019-01-01"]),
                "status": ["Active", "Active"],
            })
            synthesizer.build_assignments()
            self.assertEqual(len(synthesizer.assignments), len(synthesizer.employees))
            self.assertTrue(synthesizer.assignments["assignment_id"].is_monotonic_increasing)

            synthesizer.build_reviews()
            self.assertEqual(len(synthesizer.reviews), len(synthesizer.employees) * 3)
            self.assertTrue(synthesizer.reviews["review_score"].between(0, 100).all())

            synthesizer._inject_noise()
            self.assertIn("education_field", synthesizer.employees.columns)
            self.assertGreaterEqual(len(synthesizer.employees), 3)

            shapes = synthesizer.write_csvs()
            self.assertEqual(set(shapes), {
                "stg_employee", "stg_employee_history", "stg_project",
                "stg_assignment", "stg_review",
            })
            self.assertTrue((Path(temp_dir) / "out" / "stg_employee.csv").exists())

    def test_run_calls_stages_in_order_and_returns_export_shapes(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            synthesizer = DataSynthesizer(out_dir=temp_dir)
            stage_names = [
                "load_base", "build_employees", "build_history", "build_projects",
                "build_assignments", "build_reviews", "_inject_noise",
            ]
            with patch.multiple(
                synthesizer,
                **{name: unittest.mock.DEFAULT for name in stage_names},
            ):
                for name in stage_names:
                    getattr(synthesizer, name).side_effect = lambda: None
                with patch.object(synthesizer, "write_csvs", return_value={"stg_employee": (1, 1)}) as write:
                    self.assertEqual(synthesizer.run(), {"stg_employee": (1, 1)})
            write.assert_called_once_with()


if __name__ == "__main__":
    unittest.main()
