"""ReviewManager = performance reviews."""
from sqlalchemy.exc import IntegrityError

from src.db_manager import DatabaseManager
from src.models.review import Review


class ReviewManager(DatabaseManager):

    def add_review(self, review: Review):
        error = review.validate()
        if error:
            return False, error
        try:
            row = self.read_one(self.SILVER, "SELECT COALESCE(MAX(review_id), 0) + 1 AS next_id FROM reviews")
            review.review_id = int(row["next_id"])
            self.write(self.SILVER, """
                INSERT INTO reviews (review_id, employee_id, project_id, review_date,
                    performance_rating, review_score, job_satisfaction, work_life_balance,
                    environment_satisfaction)
                VALUES (:review_id, :employee_id, :project_id, :review_date,
                    :performance_rating, :review_score, :job_satisfaction, :work_life_balance,
                    :environment_satisfaction)
            """, review.to_dict())
            return True, (f"Review {review.review_id} saved. "
                          "Click 'Refresh warehouse' to see it in the dashboards.")
        except IntegrityError:
            return False, "Employee id or project id does not exist."
        except Exception as err:
            return False, f"Database error: {err}"

    def list_reviews(self, employee_id=None, limit=200):
        return self.read(self.SILVER, """
            SELECT r.review_id, r.employee_id, CONCAT(e.first_name, ' ', e.last_name) AS employee_name,
                   r.project_id, r.review_date, r.performance_rating, r.review_score,
                   r.job_satisfaction, r.work_life_balance, r.environment_satisfaction
            FROM reviews r JOIN employees e ON e.employee_id = r.employee_id
            WHERE :emp IS NULL OR r.employee_id = :emp
            ORDER BY r.review_date DESC LIMIT :limit
        """, {"emp": employee_id, "limit": int(limit)})