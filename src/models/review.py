from dataclasses import asdict, dataclass
from datetime import date
from typing import Optional


@dataclass
class Review:
    review_id: Optional[int]        # None for a new review
    employee_id: int
    project_id: int
    review_date: date
    performance_rating: int         # 1 to 4
    review_score: float             # 0 to 100  (change MAX_SCORE below if yours differs)
    job_satisfaction: Optional[int] = None        # 1 to 4
    work_life_balance: Optional[int] = None       # 1 to 4
    environment_satisfaction: Optional[int] = None  # 1 to 4

    MAX_SCORE = 100

    def to_dict(self):
        return asdict(self)

    def validate(self):
        if self.performance_rating not in (1, 2, 3, 4):
            return "Performance rating must be 1, 2, 3 or 4."
        if not 0 <= self.review_score <= self.MAX_SCORE:
            return f"Review score must be between 0 and {self.MAX_SCORE}."
        for value in (self.job_satisfaction, self.work_life_balance, self.environment_satisfaction):
            if value is not None and value not in (1, 2, 3, 4):
                return "Satisfaction values must be 1 to 4."
        if self.review_date > date.today():
            return "Review date cannot be in the future."
        return None