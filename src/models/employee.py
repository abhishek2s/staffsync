"""An Employee is just a bundle of data + a check that the data makes sense."""
from dataclasses import asdict, dataclass
from datetime import date
from typing import Optional


@dataclass
class Employee:
    employee_id: Optional[int]      # use None for a new employee; the database gets the next id
    first_name: str
    last_name: str
    email: str
    department_id: int
    job_role: str
    job_level: int                  # 1 to 5
    hire_date: date
    effective_from: date            # for a new employee, same as hire_date
    age: int
    monthly_income: int
    gender: Optional[str] = None
    marital_status: Optional[str] = "Single"
    attrition: Optional[str] = "No"

    @property
    def full_name(self):
        return f"{self.first_name} {self.last_name}"

    def to_dict(self):
        return asdict(self)

    def validate(self):
        """Return an error message if something is wrong, otherwise None."""
        if not self.first_name.strip() or not self.last_name.strip():
            return "First name and last name are required."
        if "@" not in self.email:
            return "Please enter a valid email address."
        if not 18 <= self.age <= 70:
            return "Age must be between 18 and 70."
        if self.job_level not in (1, 2, 3, 4, 5):
            return "Job level must be between 1 and 5."
        if self.monthly_income <= 0:
            return "Monthly income must be greater than 0."
        if self.hire_date > date.today():
            return "Hire date cannot be in the future."
        return None