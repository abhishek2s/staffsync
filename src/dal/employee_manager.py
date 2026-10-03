"""
EmployeeManager = all database work for employees.
Every method returns (True/False, "message") so Streamlit can simply do:
    ok, msg = manager.add_employee(emp)
    st.success(msg) if ok else st.error(msg)
"""
from datetime import date

from sqlalchemy.exc import IntegrityError

from src.db_manager import DatabaseManager
from src.models.employee import Employee


class EmployeeManager(DatabaseManager):      # inherits read() / write() / SILVER / GOLD

    # ---------- READ ----------
    def get_departments(self):
        return self.read(self.SILVER,
                         "SELECT department_id, department_name FROM departments ORDER BY department_name")

    def list_employees(self, search=None, limit=100):
        """search = part of a name or email (optional)."""
        pattern = f"%{search}%" if search else None
        return self.read(self.SILVER, """
            SELECT e.employee_id, e.first_name, e.last_name, e.email, d.department_name,
                   e.job_role, e.job_level, e.monthly_income, e.effective_from, e.attrition
            FROM employees e
            JOIN departments d ON d.department_id = e.department_id
            WHERE :pattern IS NULL
               OR CONCAT(e.first_name, ' ', e.last_name) LIKE :pattern
               OR e.email LIKE :pattern
            ORDER BY e.employee_id
            LIMIT :limit
        """, {"pattern": pattern, "limit": int(limit)})

    def get_employee(self, employee_id):
        """Return one employee as a dict, or None."""
        return self.read_one(self.SILVER,
                             "SELECT * FROM employees WHERE employee_id = :id", {"id": employee_id})

    # ---------- CREATE ----------
    def add_employee(self, emp: Employee):
        error = emp.validate()
        if error:
            return False, error
        try:
            # Silver ids are not auto-numbered, so we take (highest id + 1)
            row = self.read_one(self.SILVER, "SELECT COALESCE(MAX(employee_id), 0) + 1 AS next_id FROM employees")
            emp.employee_id = int(row["next_id"])
            self.write(self.SILVER, """
                INSERT INTO employees (employee_id, first_name, last_name, email, department_id,
                    job_role, job_level, hire_date, effective_from, age, gender,
                    marital_status, monthly_income, attrition)
                VALUES (:employee_id, :first_name, :last_name, :email, :department_id,
                    :job_role, :job_level, :hire_date, :effective_from, :age, :gender,
                    :marital_status, :monthly_income, :attrition)
            """, emp.to_dict())
        except IntegrityError:
            return False, "Could not save: that email already exists or the department is invalid."
        except Exception as err:
            return False, f"Database error: {err}"

        # Silver is saved. Now copy the new employee into the warehouse (SCD2 procedure).
        try:
            self.execute_procedure(self.GOLD, "sp_scd2_update")
        except Exception as err:
            return True, f"Employee {emp.employee_id} saved, but the warehouse update failed: {err}"
        return True, f"Employee {emp.employee_id} ({emp.full_name}) added."

    # ---------- UPDATE (this is the SCD Type 2 trigger) ----------
    def update_employee(self, employee_id, department_id, job_role, job_level, monthly_income):
        """
        Change department / role / level / salary.
        1. Save the new values in Silver and set effective_from = today
        2. Run sp_scd2_update -> Gold closes the OLD row (is_current = 0)
           and inserts a NEW row (is_current = 1).  That is SCD Type 2.
        """
        try:
            current = self.get_employee(employee_id)
            if current is None:
                return False, f"Employee {employee_id} not found."

            nothing_changed = (current["department_id"] == department_id
                               and current["job_role"] == job_role
                               and current["job_level"] == job_level
                               and current["monthly_income"] == monthly_income)
            if nothing_changed:
                return False, "Nothing changed - no new history record needed."
            if current["effective_from"] >= date.today():
                return False, "This employee was already changed today. Try again tomorrow."
            if job_level not in (1, 2, 3, 4, 5) or monthly_income <= 0:
                return False, "Job level must be 1-5 and income must be above 0."

            self.write(self.SILVER, """
                UPDATE employees
                SET department_id = :dept, job_role = :role, job_level = :level,
                    monthly_income = :income, effective_from = :today
                WHERE employee_id = :id
            """, {"dept": department_id, "role": job_role.strip(), "level": job_level,
                  "income": monthly_income, "today": date.today(), "id": employee_id})
        except IntegrityError:
            return False, "Invalid department selected."
        except Exception as err:
            return False, f"Database error: {err}"

        try:
            self.execute_procedure(self.GOLD, "sp_scd2_update")
        except Exception as err:
            return True, f"Saved, but the warehouse update failed: {err}"
        return True, "Employee updated and a new history record was created in the warehouse."

    # ---------- DELETE ----------
    def delete_employee(self, employee_id):
        try:
            rows = self.write(self.SILVER, "DELETE FROM employees WHERE employee_id = :id", {"id": employee_id})
            return (True, "Employee deleted.") if rows else (False, "Employee not found.")
        except Exception as err:
            return False, f"Database error: {err}"