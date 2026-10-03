"""ProjectManager = projects + assigning employees to projects."""
from datetime import date

from sqlalchemy.exc import IntegrityError

from src.db_manager import DatabaseManager
from src.models.project import Project


class ProjectManager(DatabaseManager):

    def list_projects(self, limit=200):
        return self.read(self.SILVER, """
            SELECT p.project_id, p.project_name, d.department_name, p.start_date,
                   p.planned_end_date, p.status, p.budget
            FROM projects p JOIN departments d ON d.department_id = p.department_id
            ORDER BY p.project_id DESC LIMIT :limit
        """, {"limit": int(limit)})

    def add_project(self, project: Project):
        error = project.validate()
        if error:
            return False, error
        try:
            row = self.read_one(self.SILVER, "SELECT COALESCE(MAX(project_id), 0) + 1 AS next_id FROM projects")
            project.project_id = int(row["next_id"])
            self.write(self.SILVER, """
                INSERT INTO projects (project_id, project_name, department_id, start_date,
                                      planned_end_date, status, budget)
                VALUES (:project_id, :project_name, :department_id, :start_date,
                        :planned_end_date, :status, :budget)
            """, project.to_dict())
            return True, (f"Project {project.project_id} created. "
                          "Click 'Refresh warehouse' to see it in the dashboards.")
        except IntegrityError:
            return False, "Invalid department selected."
        except Exception as err:
            return False, f"Database error: {err}"

    def assign_employee(self, employee_id, project_id, role_on_project, allocation_pct):
        """Put an employee on a project. Total allocation for one person may not exceed 100%."""
        if not role_on_project.strip():
            return False, "Role on project is required."
        if not 1 <= allocation_pct <= 100:
            return False, "Allocation must be between 1 and 100."
        try:
            already = self.read_one(self.SILVER,
                "SELECT 1 AS found FROM assignments WHERE employee_id = :e AND project_id = :p",
                {"e": employee_id, "p": project_id})
            if already:
                return False, "This employee is already on this project."

            used = self.read_one(self.SILVER,
                "SELECT COALESCE(SUM(allocation_pct), 0) AS used FROM assignments WHERE employee_id = :e",
                {"e": employee_id})["used"]
            if int(used) + allocation_pct > 100:
                return False, f"Employee already has {int(used)}% allocated. Adding {allocation_pct}% goes over 100%."

            row = self.read_one(self.SILVER, "SELECT COALESCE(MAX(assignment_id), 0) + 1 AS next_id FROM assignments")
            self.write(self.SILVER, """
                INSERT INTO assignments (assignment_id, employee_id, project_id, assigned_date,
                                         role_on_project, allocation_pct)
                VALUES (:id, :e, :p, :d, :r, :a)
            """, {"id": int(row["next_id"]), "e": employee_id, "p": project_id,
                  "d": date.today(), "r": role_on_project.strip(), "a": allocation_pct})
            return True, "Employee assigned to project."
        except IntegrityError:
            return False, "Employee id or project id does not exist."
        except Exception as err:
            return False, f"Database error: {err}"

    def list_assignments(self, project_id=None):
        return self.read(self.SILVER, """
            SELECT a.assignment_id, a.employee_id, CONCAT(e.first_name, ' ', e.last_name) AS employee_name,
                   a.project_id, a.role_on_project, a.allocation_pct, a.assigned_date
            FROM assignments a JOIN employees e ON e.employee_id = a.employee_id
            WHERE :p IS NULL OR a.project_id = :p
            ORDER BY a.assigned_date DESC LIMIT 300
        """, {"p": project_id})