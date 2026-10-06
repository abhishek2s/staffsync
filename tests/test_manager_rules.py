import unittest
from contextlib import nullcontext
from datetime import date, timedelta
from unittest.mock import patch

from sqlalchemy.exc import IntegrityError

from src.dal.employee_manager import EmployeeManager
from src.dal.project_manager import ProjectManager
from src.dal.review_manager import ReviewManager
from src.models.employee import Employee
from src.models.project import Project
from src.models.review import Review


class TestEmployeeManagerRules(unittest.TestCase):
    def setUp(self):
        self.manager = EmployeeManager()

    def make_employee(self):
        return Employee(
            None, "Ada", "Lovelace", "ada@example.com", 1, "Engineer",
            3, date.today(), date.today(), 30, 5000,
        )

    def make_current_employee(self, **changes):
        current = {
            "department_id": 1,
            "job_role": "Analyst",
            "job_level": 2,
            "monthly_income": 4000,
            "effective_from": date.today() - timedelta(days=1),
        }
        current.update(changes)
        return current

    def test_add_employee_stops_before_database_for_invalid_model(self):
        employee = self.make_employee()
        employee.email = "invalid"

        with patch.object(self.manager, "read_one") as read_one:
            ok, message = self.manager.add_employee(employee)

        self.assertFalse(ok)
        self.assertEqual(message, "Please enter a valid email address.")
        read_one.assert_not_called()

    def test_update_employee_rejects_missing_employee(self):
        conn = object()
        with (
            patch.object(self.manager, "transaction", return_value=nullcontext(conn)),
            patch.object(self.manager, "read_one", return_value=None) as read_one,
            patch.object(self.manager, "write") as write,
            patch.object(self.manager, "execute_procedure") as procedure,
        ):
            result = self.manager.update_employee(999, 1, "Engineer", 3, 5000)

        self.assertEqual(result, (False, "Employee 999 not found."))
        self.assertIs(read_one.call_args.kwargs["conn"], conn)
        write.assert_not_called()
        procedure.assert_not_called()

    def test_update_employee_rejects_unchanged_values(self):
        current = self.make_current_employee(job_role="Engineer", job_level=3, monthly_income=5000)
        with (
            patch.object(self.manager, "transaction", return_value=nullcontext(object())),
            patch.object(self.manager, "read_one", return_value=current),
            patch.object(self.manager, "write") as write,
            patch.object(self.manager, "execute_procedure") as procedure,
        ):
            result = self.manager.update_employee(1, 1, " Engineer ", 3, 5000)

        self.assertEqual(result, (False, "Nothing changed - no new history record needed."))
        write.assert_not_called()
        procedure.assert_not_called()

    def test_update_employee_rejects_second_change_on_same_day(self):
        current = self.make_current_employee(effective_from=date.today())
        with (
            patch.object(self.manager, "transaction", return_value=nullcontext(object())),
            patch.object(self.manager, "read_one", return_value=current),
        ):
            result = self.manager.update_employee(1, 2, "Engineer", 3, 5000)

        self.assertEqual(result, (False, "This employee was already changed today. Try again tomorrow."))

    def test_update_employee_rejects_invalid_job_level_and_income(self):
        current = self.make_current_employee()
        with (
            patch.object(self.manager, "transaction", return_value=nullcontext(object())),
            patch.object(self.manager, "read_one", return_value=current),
        ):
            invalid_level = self.manager.update_employee(1, 2, "Engineer", 6, 5000)
            invalid_income = self.manager.update_employee(1, 2, "Engineer", 3, 0)

        expected = (False, "Job level must be 1-5 and income must be above 0.")
        self.assertEqual(invalid_level, expected)
        self.assertEqual(invalid_income, expected)

    def test_update_employee_saves_and_refreshes_warehouse(self):
        conn = object()
        with (
            patch.object(self.manager, "transaction", return_value=nullcontext(conn)),
            patch.object(self.manager, "read_one", return_value=self.make_current_employee()),
            patch.object(self.manager, "write", return_value=1) as write,
            patch.object(self.manager, "execute_procedure") as procedure,
        ):
            result = self.manager.update_employee(1, 2, " Engineer ", 3, 5000)

        self.assertEqual(result, (True, "Employee updated and a new history record was created in the warehouse."))
        self.assertEqual(write.call_args.args[0], self.manager.SILVER)
        self.assertEqual(write.call_args.kwargs["conn"], conn)
        self.assertEqual(write.call_args.args[2]["role"], "Engineer")
        procedure.assert_called_once_with(self.manager.GOLD, "sp_scd2_update")

    def test_update_employee_reports_integrity_and_database_failures(self):
        with patch.object(
            self.manager,
            "transaction",
            side_effect=IntegrityError("update", {}, Exception()),
        ):
            integrity_result = self.manager.update_employee(1, 2, "Engineer", 3, 5000)
        self.assertEqual(integrity_result, (False, "Invalid department selected."))

        with patch.object(self.manager, "transaction", side_effect=RuntimeError("offline")):
            database_result = self.manager.update_employee(1, 2, "Engineer", 3, 5000)
        self.assertEqual(database_result, (False, "Database error: offline"))

    def test_update_employee_reports_warehouse_failure_after_saving(self):
        with (
            patch.object(self.manager, "transaction", return_value=nullcontext(object())),
            patch.object(self.manager, "read_one", return_value=self.make_current_employee()),
            patch.object(self.manager, "write", return_value=1),
            patch.object(self.manager, "execute_procedure", side_effect=RuntimeError("warehouse offline")),
        ):
            result = self.manager.update_employee(1, 2, "Engineer", 3, 5000)

        self.assertEqual(result, (True, "Saved, but the warehouse update failed: warehouse offline"))

    def test_employee_read_methods_forward_queries_and_filters(self):
        with patch.object(self.manager, "read", return_value="departments") as read:
            self.assertEqual(self.manager.get_departments(), "departments")
            self.assertEqual(read.call_args.args[0], self.manager.SILVER)

            self.manager.list_employees(search="Ada", limit="12")
            self.assertEqual(read.call_args.args[2], {"pattern": "%Ada%", "limit": 12})

            self.manager.list_employees(limit=8)
            self.assertEqual(read.call_args.args[2], {"pattern": None, "limit": 8})

        with patch.object(self.manager, "read_one", return_value={"employee_id": 1}) as read_one:
            self.assertEqual(self.manager.get_employee(1), {"employee_id": 1})
        self.assertEqual(read_one.call_args.args[2], {"id": 1})

    def test_add_employee_saves_and_handles_database_failures(self):
        employee = self.make_employee()
        conn = object()
        with (
            patch.object(self.manager, "transaction", return_value=nullcontext(conn)),
            patch.object(self.manager, "read_one", return_value={"next_id": 12}),
            patch.object(self.manager, "write") as write,
            patch.object(self.manager, "execute_procedure") as procedure,
        ):
            result = self.manager.add_employee(employee)

        self.assertTrue(result[0])
        self.assertEqual(result[1], "Employee 12 (Ada Lovelace) added.")
        self.assertEqual(employee.employee_id, 12)
        self.assertEqual(write.call_args.args[0], self.manager.SILVER)
        self.assertEqual(write.call_args.kwargs["conn"], conn)
        procedure.assert_called_once_with(self.manager.GOLD, "sp_scd2_update")

        employee = self.make_employee()
        with patch.object(
            self.manager,
            "transaction",
            side_effect=IntegrityError("insert", {}, Exception()),
        ):
            result = self.manager.add_employee(employee)
        self.assertEqual(
            result,
            (False, "Could not save: that email already exists or the department is invalid."),
        )

        employee = self.make_employee()
        with patch.object(self.manager, "transaction", side_effect=RuntimeError("offline")):
            result = self.manager.add_employee(employee)
        self.assertEqual(result, (False, "Database error: offline"))

    def test_add_employee_reports_warehouse_failure_after_saving(self):
        employee = self.make_employee()
        with (
            patch.object(self.manager, "transaction", return_value=nullcontext(object())),
            patch.object(self.manager, "read_one", return_value={"next_id": 12}),
            patch.object(self.manager, "write"),
            patch.object(self.manager, "execute_procedure", side_effect=RuntimeError("offline")),
        ):
            result = self.manager.add_employee(employee)

        self.assertEqual(result, (True, "Employee 12 saved, but the warehouse update failed: offline"))

    def test_delete_employee_reports_deleted_missing_and_database_error(self):
        with patch.object(self.manager, "write", return_value=1):
            self.assertEqual(self.manager.delete_employee(1), (True, "Employee deleted."))
        with patch.object(self.manager, "write", return_value=0):
            self.assertEqual(self.manager.delete_employee(999), (False, "Employee not found."))
        with patch.object(self.manager, "write", side_effect=RuntimeError("offline")):
            self.assertEqual(self.manager.delete_employee(1), (False, "Database error: offline"))


class TestProjectManagerRules(unittest.TestCase):
    def setUp(self):
        self.manager = ProjectManager()

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

    def test_assignment_requires_role(self):
        result = self.manager.assign_employee(1, 1, " ", 25)
        self.assertEqual(result, (False, "Role on project is required."))

    def test_assignment_rejects_invalid_allocation(self):
        result = self.manager.assign_employee(1, 1, "Engineer", 0)
        self.assertEqual(result, (False, "Allocation must be between 1 and 100."))

    def test_assignment_rejects_overallocation(self):
        with (
            patch.object(self.manager, "transaction", return_value=nullcontext(object())),
            patch.object(self.manager, "read_one", side_effect=[None, {"used": 90}]),
            patch.object(self.manager, "write") as write,
        ):
            result = self.manager.assign_employee(1, 2, "Engineer", 20)

        self.assertEqual(
            result,
            (False, "Employee already has 90% allocated. Adding 20% goes over 100%."),
        )
        write.assert_not_called()

    def test_assignment_rejects_duplicate_project_assignment(self):
        with (
            patch.object(self.manager, "transaction", return_value=nullcontext(object())),
            patch.object(self.manager, "read_one", return_value={"found": 1}),
            patch.object(self.manager, "write") as write,
        ):
            result = self.manager.assign_employee(1, 2, "Engineer", 25)

        self.assertEqual(result, (False, "This employee is already on this project."))
        write.assert_not_called()

    def test_project_read_methods_forward_filters_and_limits(self):
        with patch.object(self.manager, "read", return_value="rows") as read:
            self.assertEqual(self.manager.list_projects(search="Cloud", employee_id=7, limit="9"), "rows")
            self.assertEqual(read.call_args.args[2], {
                "pattern": "%Cloud%", "project_id": None, "employee_id": 7, "limit": 9,
            })

            self.manager.list_projects(search="42")
            self.assertEqual(read.call_args.args[2]["pattern"], None)
            self.assertEqual(read.call_args.args[2]["project_id"], 42)

            self.manager.list_projects(search="")
            self.assertEqual(read.call_args.args[2]["project_id"], None)

        with patch.object(self.manager, "read", return_value="employee projects") as read:
            self.assertEqual(self.manager.list_employee_projects("7", limit="5"), "employee projects")
        self.assertEqual(read.call_args.args[2], {"employee_id": 7, "limit": 5})

        with patch.object(self.manager, "read", return_value="assignments") as read:
            self.assertEqual(self.manager.list_assignments(3), "assignments")
        self.assertEqual(read.call_args.args[2], {"p": 3})

    def test_add_project_validates_and_saves_project(self):
        invalid = self.make_project(project_name="")
        self.assertEqual(self.manager.add_project(invalid), (False, "Project name is required."))

        project = self.make_project()
        conn = object()
        with (
            patch.object(self.manager, "transaction", return_value=nullcontext(conn)),
            patch.object(self.manager, "read_one", return_value={"next_id": 4}),
            patch.object(self.manager, "write") as write,
        ):
            result = self.manager.add_project(project)

        self.assertEqual(
            result,
            (True, "Project 4 created. Click 'Refresh warehouse' to see it in the dashboards."),
        )
        self.assertEqual(project.project_id, 4)
        self.assertEqual(write.call_args.kwargs["conn"], conn)

    def test_add_project_reports_integrity_and_database_errors(self):
        project = self.make_project()
        with patch.object(
            self.manager,
            "transaction",
            side_effect=IntegrityError("insert", {}, Exception()),
        ):
            result = self.manager.add_project(project)
        self.assertEqual(result, (False, "Invalid department selected."))

        with patch.object(self.manager, "transaction", side_effect=RuntimeError("offline")):
            result = self.manager.add_project(project)
        self.assertEqual(result, (False, "Database error: offline"))

    def test_assignment_success_and_database_errors(self):
        conn = object()
        with (
            patch.object(self.manager, "transaction", return_value=nullcontext(conn)),
            patch.object(self.manager, "read_one", side_effect=[
                None, {"used": 50}, {"next_id": 8},
            ]),
            patch.object(self.manager, "write") as write,
        ):
            result = self.manager.assign_employee(1, 2, " Engineer ", 50)

        self.assertEqual(result, (True, "Employee assigned to project."))
        self.assertEqual(write.call_args.args[2]["id"], 8)
        self.assertEqual(write.call_args.args[2]["r"], "Engineer")
        self.assertEqual(write.call_args.kwargs["conn"], conn)

        with patch.object(self.manager, "transaction", side_effect=IntegrityError("insert", {}, Exception())):
            result = self.manager.assign_employee(1, 2, "Engineer", 50)
        self.assertEqual(result, (False, "Employee id or project id does not exist."))

        with patch.object(self.manager, "transaction", side_effect=RuntimeError("offline")):
            result = self.manager.assign_employee(1, 2, "Engineer", 50)
        self.assertEqual(result, (False, "Database error: offline"))

class TestReviewManagerRules(unittest.TestCase):
    def setUp(self):
        self.manager = ReviewManager()

    def make_review(self, **changes):
        values = {
            "review_id": None,
            "employee_id": 1,
            "project_id": 1,
            "review_date": date.today(),
            "performance_rating": 3,
            "review_score": 80,
        }
        values.update(changes)
        return Review(**values)

    def test_add_review_rejects_invalid_model_before_database_access(self):
        review = self.make_review(performance_rating=5)

        with patch.object(self.manager, "read_one") as read_one:
            result = self.manager.add_review(review)

        self.assertEqual(result, (False, "Performance rating must be 1, 2, 3 or 4."))
        read_one.assert_not_called()

    def test_add_review_saves_review(self):
        review = self.make_review()
        conn = object()
        with (
            patch.object(self.manager, "transaction", return_value=nullcontext(conn)),
            patch.object(self.manager, "read_one", return_value={"next_id": 11}),
            patch.object(self.manager, "write") as write,
        ):
            result = self.manager.add_review(review)

        self.assertEqual(
            result,
            (True, "Review 11 saved. Click 'Refresh warehouse' to see it in the dashboards."),
        )
        self.assertEqual(review.review_id, 11)
        self.assertEqual(write.call_args.kwargs["conn"], conn)

    def test_add_review_reports_integrity_and_database_errors(self):
        with patch.object(
            self.manager,
            "transaction",
            side_effect=IntegrityError("insert", {}, Exception()),
        ):
            result = self.manager.add_review(self.make_review())
        self.assertEqual(result, (False, "Employee id or project id does not exist."))

        with patch.object(self.manager, "transaction", side_effect=RuntimeError("offline")):
            result = self.manager.add_review(self.make_review())
        self.assertEqual(result, (False, "Database error: offline"))

    def test_list_reviews_forwards_filters(self):
        with patch.object(self.manager, "read", return_value="reviews") as read:
            self.assertEqual(self.manager.list_reviews(employee_id=4, limit="6"), "reviews")
        self.assertEqual(read.call_args.args[2], {"emp": 4, "limit": 6})


if __name__ == "__main__":
    unittest.main()
