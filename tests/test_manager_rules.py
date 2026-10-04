import unittest
from datetime import date
from unittest.mock import Mock, patch

from src.dal.employee_manager import EmployeeManager
from src.dal.project_manager import ProjectManager
from src.dal.review_manager import ReviewManager
from src.models.employee import Employee
from src.models.review import Review


class TestEmployeeManagerRules(unittest.TestCase):
    def make_employee(self):
        return Employee(
            None, "Ada", "Lovelace", "ada@example.com", 1, "Engineer",
            3, date.today(), date.today(), 30, 5000,
        )

    def test_add_employee_stops_before_database_for_invalid_model(self):
        manager = EmployeeManager()
        employee = self.make_employee()
        employee.email = "invalid"

        with patch.object(manager, "read_one") as read_one:
            ok, message = manager.add_employee(employee)

        self.assertFalse(ok)
        self.assertEqual(message, "Please enter a valid email address.")
        read_one.assert_not_called()

    def test_update_employee_rejects_missing_employee(self):
        manager = EmployeeManager()
        with patch.object(manager, "get_employee", return_value=None):
            result = manager.update_employee(999, 1, "Engineer", 3, 5000)

        self.assertEqual(result, (False, "Employee 999 not found."))


class TestProjectManagerRules(unittest.TestCase):
    def test_assignment_requires_role(self):
        manager = ProjectManager()
        result = manager.assign_employee(1, 1, " ", 25)
        self.assertEqual(result, (False, "Role on project is required."))

    def test_assignment_rejects_invalid_allocation(self):
        manager = ProjectManager()
        result = manager.assign_employee(1, 1, "Engineer", 0)
        self.assertEqual(result, (False, "Allocation must be between 1 and 100."))

    def test_assignment_rejects_overallocation(self):
        manager = ProjectManager()
        manager.read_one = Mock(side_effect=[
            None,
            {"used": 90},
        ])

        result = manager.assign_employee(1, 2, "Engineer", 20)

        self.assertEqual(
            result,
            (False, "Employee already has 90% allocated. Adding 20% goes over 100%."),
        )

    def test_assignment_rejects_duplicate_project_assignment(self):
        manager = ProjectManager()
        manager.read_one = Mock(return_value={"found": 1})

        result = manager.assign_employee(1, 2, "Engineer", 25)

        self.assertEqual(result, (False, "This employee is already on this project."))


class TestReviewManagerRules(unittest.TestCase):
    def test_add_review_rejects_invalid_model_before_database_access(self):
        manager = ReviewManager()
        review = Review(
            review_id=None,
            employee_id=1,
            project_id=1,
            review_date=date.today(),
            performance_rating=5,
            review_score=80,
        )

        with patch.object(manager, "read_one") as read_one:
            result = manager.add_review(review)

        self.assertEqual(result, (False, "Performance rating must be 1, 2, 3 or 4."))
        read_one.assert_not_called()


if __name__ == "__main__":
    unittest.main()
