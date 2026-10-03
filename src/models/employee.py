from __future__ import annotations

from dataclasses import dataclass
from datetime import date
from typing import Optional


@dataclass
class Employee:
    employee_id: int
    first_name: str
    last_name: str
    email: str
    department_id: int
    job_role: str
    job_level: int
    hire_date: date
    effective_from: date
    age: int
    monthly_income: int
    gender: Optional[str] = None
    marital_status: Optional[str] = "Single"
    attrition: Optional[str] = "No"

    @property
    def full_name(self) -> str:
        return f"{self.first_name} {self.last_name}"