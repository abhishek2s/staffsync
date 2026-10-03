-- ============================================================================
-- STORED PROCEDURE: Silver + Bronze -> Gold dimensional warehouse
-- ============================================================================
USE staffsync_gold;

DELIMITER $$

DROP PROCEDURE IF EXISTS sp_populate_olap$$

CREATE PROCEDURE sp_populate_olap()
BEGIN
    -- The fact table is rebuilt from the current Silver review transaction set.
    DELETE FROM fact_performance_reviews;

    -- 1. Populate the conformed department dimension.
    INSERT INTO dim_department (department_id, department_name)
    SELECT
        d.department_id,
        d.department_name
    FROM staffsync_silver.departments d
    ON DUPLICATE KEY UPDATE
        department_name = VALUES(department_name);

    -- 2. Populate the project dimension.
    INSERT INTO dim_project (
        project_id, project_name, department_key, project_start_date,
        planned_end_date, status, budget
    )
    SELECT
        p.project_id,
        TRIM(p.project_name),
        dd.department_key,
        p.start_date,
        p.planned_end_date,
        p.status,
        p.budget
    FROM staffsync_silver.projects p
    JOIN dim_department dd
        ON dd.department_id = p.department_id
    ON DUPLICATE KEY UPDATE
        project_name = VALUES(project_name),
        department_key = VALUES(department_key),
        project_start_date = VALUES(project_start_date),
        planned_end_date = VALUES(planned_end_date),
        status = VALUES(status),
        budget = VALUES(budget);

    -- 3. Populate dates used by reviews. This avoids a recursive day-by-day
    --    CTE, which can exceed MySQL's default recursive query depth.
    INSERT INTO dim_date (
        date_key, full_date, day_of_month, month_number, month_name,
        quarter_number, year_number, week_number, day_name
    )
    SELECT
        CAST(DATE_FORMAT(full_date, '%Y%m%d') AS UNSIGNED),
        full_date,
        DAY(full_date),
        MONTH(full_date),
        MONTHNAME(full_date),
        QUARTER(full_date),
        YEAR(full_date),
        WEEK(full_date, 3),
        DAYNAME(full_date)
    FROM (
        SELECT DISTINCT review_date AS full_date
        FROM staffsync_silver.reviews
        WHERE review_date IS NOT NULL
    ) review_dates
    WHERE full_date IS NOT NULL
    ON DUPLICATE KEY UPDATE
        day_of_month = VALUES(day_of_month),
        month_number = VALUES(month_number),
        month_name = VALUES(month_name),
        quarter_number = VALUES(quarter_number),
        year_number = VALUES(year_number),
        week_number = VALUES(week_number),
        day_name = VALUES(day_name);

    -- 4. Build or incrementally update employee SCD Type 2 versions.
    CALL sp_scd2_update();

    -- 5. Load the review fact table. The window function protects the fact
    --    grain if overlapping source versions are ever encountered.
    INSERT INTO fact_performance_reviews (
        review_id, employee_key, project_key, date_key, department_key,
        performance_rating, review_score, job_satisfaction,
        work_life_balance, environment_satisfaction, review_count
    )
    WITH ranked_reviews AS (
        SELECT
            r.review_id,
            e.employee_key,
            p.project_key,
            d.date_key,
            e.department_key,
            r.performance_rating,
            r.review_score,
            r.job_satisfaction,
            r.work_life_balance,
            r.environment_satisfaction,
            ROW_NUMBER() OVER (
                PARTITION BY r.review_id
                ORDER BY e.start_date DESC, e.employee_key DESC
            ) AS version_rank
        FROM staffsync_silver.reviews r
        JOIN dim_employee e
            ON e.employee_id = r.employee_id
           AND r.review_date BETWEEN e.start_date AND e.end_date
        JOIN dim_project p
            ON p.project_id = r.project_id
        JOIN dim_date d
            ON d.full_date = r.review_date
    )
    SELECT
        review_id,
        employee_key,
        project_key,
        date_key,
        department_key,
        performance_rating,
        review_score,
        job_satisfaction,
        work_life_balance,
        environment_satisfaction,
        1
    FROM ranked_reviews
    WHERE version_rank = 1;
END$$

DELIMITER ;
