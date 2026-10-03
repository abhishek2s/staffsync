-- ============================================================================
-- GOLD LAYER: Analytical KPI Views
-- ============================================================================
USE staffsync_gold;

DROP VIEW IF EXISTS vw_project_bottleneck;
DROP VIEW IF EXISTS vw_employee_attrition_performance;
DROP VIEW IF EXISTS vw_top_employees_by_department;
DROP VIEW IF EXISTS vw_yoy_performance;

-- Year-over-year performance by department.
CREATE VIEW vw_yoy_performance AS
SELECT
    d.year_number AS review_year,
    dept.department_name,
    COUNT(DISTINCT f.review_id) AS review_count,
    ROUND(AVG(f.review_score), 2) AS average_review_score,
    ROUND(AVG(f.performance_rating), 2) AS average_performance_rating,
    ROUND(
        AVG(f.review_score)
        - LAG(AVG(f.review_score)) OVER (
            PARTITION BY dept.department_key
            ORDER BY d.year_number
        ),
        2
    ) AS score_change_from_prior_year
FROM fact_performance_reviews f
JOIN dim_date d
    ON d.date_key = f.date_key
JOIN dim_department dept
    ON dept.department_key = f.department_key
GROUP BY d.year_number, dept.department_key, dept.department_name;

-- Top employees within each department and review year.
CREATE VIEW vw_top_employees_by_department AS
WITH employee_scores AS (
    SELECT
        d.year_number AS review_year,
        dept.department_name,
        e.employee_id,
        CONCAT(e.first_name, ' ', e.last_name) AS employee_name,
        ROUND(AVG(f.review_score), 2) AS average_review_score,
        DENSE_RANK() OVER (
            PARTITION BY d.year_number, dept.department_key
            ORDER BY AVG(f.review_score) DESC
        ) AS department_rank
    FROM fact_performance_reviews f
    JOIN dim_employee e
        ON e.employee_key = f.employee_key
    JOIN dim_date d
        ON d.date_key = f.date_key
    JOIN dim_department dept
        ON dept.department_key = f.department_key
    GROUP BY
        d.year_number,
        dept.department_key,
        dept.department_name,
        e.employee_id,
        e.first_name,
        e.last_name
)
SELECT *
FROM employee_scores
WHERE department_rank <= 10;

-- Current employee attrition context alongside review performance.
CREATE VIEW vw_employee_attrition_performance AS
SELECT
    e.employee_id,
    CONCAT(e.first_name, ' ', e.last_name) AS employee_name,
    dept.department_name,
    e.job_role,
    e.attrition,
    COUNT(DISTINCT f.review_id) AS review_count,
    ROUND(AVG(f.review_score), 2) AS average_review_score,
    ROUND(AVG(f.job_satisfaction), 2) AS average_job_satisfaction,
    ROUND(AVG(f.work_life_balance), 2) AS average_work_life_balance
FROM dim_employee e
JOIN dim_department dept
    ON dept.department_key = e.department_key
LEFT JOIN fact_performance_reviews f
    ON f.employee_key = e.employee_key
WHERE e.is_current = TRUE
GROUP BY
    e.employee_id,
    e.first_name,
    e.last_name,
    dept.department_name,
    e.job_role,
    e.attrition;

-- Project workload and review pressure indicators.
CREATE VIEW vw_project_bottleneck AS
WITH assignment_summary AS (
    SELECT
        project_id,
        COUNT(DISTINCT employee_id) AS assigned_employee_count,
        SUM(allocation_pct) AS total_allocation_pct
    FROM staffsync_silver.assignments
    GROUP BY project_id
), review_summary AS (
    SELECT
        project_key,
        COUNT(*) AS review_count,
        ROUND(AVG(review_score), 2) AS average_review_score
    FROM fact_performance_reviews
    GROUP BY project_key
)
SELECT
    p.project_id,
    p.project_name,
    dept.department_name,
    p.status,
    p.budget,
    COALESCE(a.assigned_employee_count, 0) AS assigned_employee_count,
    COALESCE(a.total_allocation_pct, 0) AS total_allocation_pct,
    COALESCE(r.review_count, 0) AS review_count,
    r.average_review_score
FROM dim_project p
JOIN dim_department dept
    ON dept.department_key = p.department_key
LEFT JOIN assignment_summary a
    ON a.project_id = p.project_id
LEFT JOIN review_summary r
    ON r.project_key = p.project_key;
