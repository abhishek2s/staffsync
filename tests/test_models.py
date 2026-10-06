import unittest
from datetime import date, timedelta

from src.models.employee import Employee
from src.models.project import Project
from src.models.review import Review


class TestEmployeeValidation(unittest.TestCase):
    def make_employee(self, **changes):
        values = {
            "employee_id": None,
            "first_name": "Ada",
            "last_name": "Lovelace",
            "email": "ada@example.com",
            "department_id": 1,
            "job_role": "Engineer",
            "job_level": 3,
            "hire_date": date.today(),
            "effective_from": date.today(),
            "age": 30,
            "monthly_income": 5000,
        }
        values.update(changes)
        return Employee(**values)

    def test_valid_employee_has_full_name_and_no_validation_error(self):
        employee = self.make_employee()
        self.assertEqual(employee.full_name, "Ada Lovelace")
        self.assertIsNone(employee.validate())

    def test_employee_rejects_invalid_email(self):
        self.assertEqual(
            self.make_employee(email="invalid").validate(),
            "Please enter a valid email address.",
        )

    def test_employee_rejects_numbers_in_first_name(self):
        self.assertEqual(
            self.make_employee(first_name="12333").validate(),
            "First name must contain letters only.",
        )

    def test_employee_rejects_numbers_in_last_name(self):
        self.assertEqual(
            self.make_employee(last_name="12333").validate(),
            "Last name must contain letters only.",
        )

    def test_employee_rejects_numbers_in_job_role(self):
        self.assertEqual(
            self.make_employee(job_role="12333").validate(),
            "Job role must contain letters only.",
        )

    def test_employee_rejects_empty_job_role(self):
        self.assertEqual(
            self.make_employee(job_role="").validate(),
            "Job role is required.",
        )

    def test_employee_rejects_email_without_valid_local_part(self):
        self.assertEqual(
            self.make_employee(email="abc*gmail.com").validate(),
            "Please enter a valid email address.",
        )

    def test_employee_accepts_standard_email(self):
        self.assertIsNone(self.make_employee(email="abc@gmail.com").validate())

    def test_employee_rejects_future_hire_date(self):
        self.assertEqual(
            self.make_employee(hire_date=date.today() + timedelta(days=1)).validate(),
            "Hire date cannot be in the future.",
        )

    def test_employee_rejects_blank_names(self):
        for changes in ({"first_name": " "}, {"last_name": " "}):
            with self.subTest(changes=changes):
                self.assertEqual(
                    self.make_employee(**changes).validate(),
                    "First name and last name are required.",
                )

    def test_employee_rejects_age_outside_allowed_range(self):
        for age in (17, 71):
            with self.subTest(age=age):
                self.assertEqual(
                    self.make_employee(age=age).validate(),
                    "Age must be between 18 and 70.",
                )

    def test_employee_rejects_invalid_job_level(self):
        self.assertEqual(
            self.make_employee(job_level=6).validate(),
            "Job level must be between 1 and 5.",
        )

    def test_employee_rejects_nonpositive_income(self):
        self.assertEqual(
            self.make_employee(monthly_income=0).validate(),
            "Monthly income must be greater than 0.",
        )

    def test_employee_serializes_all_fields(self):
        employee = self.make_employee()
        self.assertEqual(employee.to_dict()["email"], "ada@example.com")
        self.assertIsNone(employee.to_dict()["gender"])


class TestProjectValidation(unittest.TestCase):
    def make_project(self, **changes):
        values = {
            "project_id": None,
            "project_name": "Platform migration",
            "department_id": 1,
            "start_date": date.today(),
            "planned_end_date": date.today() + timedelta(days=30),
            "status": "Planned",
            "budget": 10000,
        }
        values.update(changes)
        return Project(**values)

    def test_project_rejects_end_date_before_start_date(self):
        project = self.make_project(planned_end_date=date.today() - timedelta(days=1))
        self.assertEqual(
            project.validate(),
            "Planned end date must be after the start date.",
        )

    def test_project_rejects_end_date_equal_to_start_date(self):
        self.assertEqual(
            self.make_project(planned_end_date=date.today()).validate(),
            "Planned end date must be after the start date.",
        )

    def test_project_rejects_negative_budget(self):
        self.assertEqual(
            self.make_project(budget=-1).validate(),
            "Budget cannot be negative.",
        )

    def test_project_rejects_name_without_letters(self):
        self.assertEqual(
            self.make_project(project_name="0000").validate(),
            "Project name is invalid. Please include at least one letter.",
        )


class TestReviewValidation(unittest.TestCase):
    def make_review(self, **changes):
        values = {
            "review_id": None,
            "employee_id": 1,
            "project_id": 1,
            "review_date": date.today(),
            "performance_rating": 3,
            "review_score": 80,
            "job_satisfaction": 3,
            "work_life_balance": 3,
            "environment_satisfaction": 3,
        }
        values.update(changes)
        return Review(**values)

    def test_review_rejects_score_above_maximum(self):
        self.assertEqual(
            self.make_review(review_score=101).validate(),
            "Review score must be between 0 and 100.",
        )

    def test_review_rejects_future_date(self):
        self.assertEqual(
            self.make_review(review_date=date.today() + timedelta(days=1)).validate(),
            "Review date cannot be in the future.",
        )

    def test_review_rejects_invalid_satisfaction_rating(self):
        self.assertEqual(
            self.make_review(job_satisfaction=5).validate(),
            "Satisfaction values must be 1 to 4.",
        )

    def test_review_serializes_fields(self):
        review = self.make_review()
        self.assertEqual(review.to_dict()["review_score"], 80)


if __name__ == "__main__":
    unittest.main()
