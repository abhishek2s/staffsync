"""
AnalyticsManager = everything the dashboard shows. It only READS from the Gold
warehouse (star schema + the views in kpi_views.sql). Each method returns either
a DataFrame (for charts/tables) or a dict (for KPI cards).
"""
from src.db_manager import DatabaseManager


class AnalyticsManager(DatabaseManager):

    # ============ KPI CARDS ============
    def get_kpis(self):
        """Headline numbers. In Streamlit:  st.metric("Employees", kpis["total_employees"])"""
        emp = self.read_one(self.GOLD, """
            SELECT COUNT(*) AS total,
                   COALESCE(SUM(attrition = 'Yes'), 0) AS left_company
            FROM dim_employee WHERE is_current = TRUE""")
        rev = self.read_one(self.GOLD, """
            SELECT COUNT(*) AS total, AVG(review_score) AS avg_score,
                   AVG(performance_rating) AS avg_rating,
                   AVG(job_satisfaction) AS avg_job_sat, AVG(work_life_balance) AS avg_wlb
            FROM fact_performance_reviews""")
        proj = self.read_one(self.GOLD, "SELECT COUNT(*) AS total, COALESCE(SUM(budget), 0) AS budget FROM dim_project")
        over = self.read_one(self.GOLD, f"""
            SELECT COUNT(*) AS total FROM (
                SELECT employee_id FROM {self.SILVER}.assignments
                GROUP BY employee_id HAVING SUM(allocation_pct) > 100
            ) t""")

        total = int(emp["total"])
        left = int(emp["left_company"])
        return {
            "total_employees": total,
            "attrition_rate_pct": round(100 * left / total, 2) if total else 0,
            "total_reviews": int(rev["total"]),
            "avg_review_score": round(float(rev["avg_score"] or 0), 2),
            "avg_performance_rating": round(float(rev["avg_rating"] or 0), 2),
            "avg_job_satisfaction": round(float(rev["avg_job_sat"] or 0), 2),
            "avg_work_life_balance": round(float(rev["avg_wlb"] or 0), 2),
            "total_projects": int(proj["total"]),
            "total_project_budget": float(proj["budget"]),
            "overallocated_employees": int(over["total"]),
        }

    # ============ DROPDOWN HELPERS ============
    def get_years(self):
        df = self.read(self.GOLD, "SELECT DISTINCT year_number FROM dim_date ORDER BY year_number DESC")
        return df["year_number"].tolist()

    def get_department_names(self):
        df = self.read(self.GOLD, "SELECT department_name FROM dim_department ORDER BY department_name")
        return df["department_name"].tolist()

    # ============ YEAR-OVER-YEAR (uses LAG in the view) ============
    def yoy_performance(self, department=None):
        """Score per year per department. Column score_change_from_prior_year = the YoY change."""
        return self.read(self.GOLD, """
            SELECT * FROM vw_yoy_performance
            WHERE :dept IS NULL OR department_name = :dept
            ORDER BY department_name, review_year
        """, {"dept": department})

    def yoy_overall(self):
        """Company-wide score per year (one line chart)."""
        return self.read(self.GOLD, """
            SELECT d.year_number AS review_year, COUNT(*) AS review_count,
                   ROUND(AVG(f.review_score), 2) AS average_review_score
            FROM fact_performance_reviews f JOIN dim_date d ON d.date_key = f.date_key
            GROUP BY d.year_number ORDER BY d.year_number
        """)

    # ============ TOP EMPLOYEES (uses DENSE_RANK in the view) ============
    def top_employees(self, year=None, department=None, top_n=10):
        """The view already keeps only the top 10, so top_n can be 1 to 10."""
        return self.read(self.GOLD, """
            SELECT review_year, department_name, employee_id, employee_name,
                   average_review_score, department_rank
            FROM vw_top_employees_by_department
            WHERE department_rank <= :n
              AND (:yr IS NULL OR review_year = :yr)
              AND (:dept IS NULL OR department_name = :dept)
            ORDER BY review_year DESC, department_name, department_rank
        """, {"n": int(top_n), "yr": year, "dept": department})

    # ============ ATTRITION ============
    def attrition_by_department(self):
        return self.read(self.GOLD, """
            SELECT department_name,
                   COUNT(*) AS employees,
                   SUM(attrition = 'Yes') AS left_company,
                   ROUND(100 * SUM(attrition = 'Yes') / COUNT(*), 2) AS attrition_rate_pct,
                   ROUND(AVG(average_review_score), 2) AS avg_review_score
            FROM vw_employee_attrition_performance
            GROUP BY department_name
            ORDER BY attrition_rate_pct DESC
        """)

    def attrition_risk(self, top_n=25):
        """
        Current employees who might leave. Simple rule:
            risk_score = (4 - job satisfaction) + (4 - work-life balance)   -> 0 to 6
        6 = very unhappy, 0 = very happy.  High >= 4, Medium >= 3, otherwise Low.
        """
        return self.read(self.GOLD, """
            SELECT *,
                   CASE WHEN risk_score >= 4 THEN 'High'
                        WHEN risk_score >= 3 THEN 'Medium'
                        ELSE 'Low' END AS risk_level
            FROM (
                SELECT employee_id, employee_name, department_name, job_role,
                       average_review_score, average_job_satisfaction, average_work_life_balance,
                       ROUND((4 - average_job_satisfaction) + (4 - average_work_life_balance), 2) AS risk_score
                FROM vw_employee_attrition_performance
                WHERE attrition = 'No' AND review_count > 0
                  AND average_job_satisfaction IS NOT NULL
                  AND average_work_life_balance IS NOT NULL
            ) scored
            ORDER BY risk_score DESC
            LIMIT :n
        """, {"n": int(top_n)})

    # ============ PROJECT BOTTLENECKS ============
    def project_bottlenecks(self):
        """
        Reads vw_project_bottleneck and adds a 'flag' column:
            Busy       = people on this project are allocated more than most projects (top 25%)
            Low scores = review scores are lower than most projects (bottom 25%)
            Critical   = both of the above
        """
        df = self.read(self.GOLD, "SELECT * FROM vw_project_bottleneck")
        if df.empty:
            return df
        people = df["assigned_employee_count"].where(df["assigned_employee_count"] > 0)  # avoid dividing by 0
        df["avg_allocation_pct"] = (df["total_allocation_pct"] / people).round(2)

        busy = df["avg_allocation_pct"] >= df["avg_allocation_pct"].quantile(0.75)
        weak = df["average_review_score"] <= df["average_review_score"].quantile(0.25)

        df["flag"] = "OK"
        df.loc[busy, "flag"] = "Busy"
        df.loc[weak, "flag"] = "Low scores"
        df.loc[busy & weak, "flag"] = "Critical"
        return df.sort_values("avg_allocation_pct", ascending=False)

    def project_status_counts(self):
        return self.read(self.GOLD, """
            SELECT status, COUNT(*) AS projects, ROUND(SUM(budget), 2) AS total_budget
            FROM dim_project GROUP BY status ORDER BY projects DESC
        """)

    # ============ SCD TYPE 2 HISTORY ============
    def employee_history(self, employee_id):
        """Every version of one employee: old rows have is_current = 0."""
        return self.read(self.GOLD, """
            SELECT e.employee_id, d.department_name, e.job_role, e.job_level, e.monthly_income,
                   e.start_date, e.end_date, e.is_current
            FROM dim_employee e JOIN dim_department d ON d.department_key = e.department_key
            WHERE e.employee_id = :id
            ORDER BY e.start_date
        """, {"id": employee_id})

    # ============ REFRESH BUTTON ============
    def refresh_warehouse(self):
        """Re-run the full Silver -> Gold load (picks up new projects and reviews). Takes a while."""
        try:
            self.execute_procedure(self.GOLD, "sp_populate_olap")
            return True, "Warehouse refreshed."
        except Exception as err:
            return False, f"Refresh failed: {err}"