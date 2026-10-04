from dataclasses import asdict, dataclass
from datetime import date
import re
from typing import Optional


@dataclass
class Project:
    project_id: Optional[int]       # None for a new project
    project_name: str
    department_id: int
    start_date: date
    planned_end_date: date
    status: str
    budget: float

    def to_dict(self):
        return asdict(self)

    def validate(self):
        if not self.project_name.strip():
            return "Project name is required."
        if not re.fullmatch(r"(?=.*[A-Za-z])[A-Za-z0-9][A-Za-z0-9 '&/_().-]*", self.project_name.strip()):
            return "Project name is invalid. Please include at least one letter."
        if self.planned_end_date <= self.start_date:
            return "Planned end date must be after the start date."
        if self.budget < 0:
            return "Budget cannot be negative."
        return None