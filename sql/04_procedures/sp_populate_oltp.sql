-- STORED PROCEDURE: Bronze (Staging) -> Silver (3NF OLTP)
-- Handles cleaning, deduplication, casing normalization, and FK population

USE staffsync_silver;

DELIMITER $$

DROP PROCEDURE IF EXISTS sp_populate_oltp$$

CREATE PROCEDURE sp_populate_oltp()
BEGIN
    -- Disable foreign key checks for clean bulk truncation/population
    SET FOREIGN_KEY_CHECKS = 0;
    TRUNCATE TABLE reviews;
    TRUNCATE TABLE assignments;
    TRUNCATE TABLE projects;
    TRUNCATE TABLE employees;
    TRUNCATE TABLE departments;
    SET FOREIGN_KEY_CHECKS = 1;

    -- 1. Populate Departments Lookup
    INSERT INTO departments (department_name)
    SELECT DISTINCT 
        CONCAT(UPPER(LEFT(TRIM(department), 1)), LOWER(SUBSTRING(TRIM(department), 2))) AS department_name
    FROM staffsync_bronze.stg_employee
    WHERE department IS NOT NULL AND TRIM(department) <> ''
    ON DUPLICATE KEY UPDATE department_name = VALUES(department_name);

    -- 2. Clean, Deduplicate (ROW_NUMBER CTE), and Populate Employees
    INSERT INTO employees (
        employee_id, first_name, last_name, email, department_id,
        job_role, job_level, hire_date, effective_from, age,
        gender, marital_status, monthly_income, attrition
    )
    WITH CleanedEmployees AS (
        SELECT 
            e.employee_id,
            TRIM(e.first_name) AS first_name,
            TRIM(e.last_name) AS last_name,
            LOWER(TRIM(e.email)) AS email,
            d.department_id,
            TRIM(e.job_role) AS job_role,
            e.job_level,
            e.hire_date,
            e.effective_from,
            e.age,
            e.gender,
            COALESCE(e.marital_status, 'Single') AS marital_status,
            e.monthly_income,
            e.attrition,
            ROW_NUMBER() OVER (
                PARTITION BY e.employee_id 
                ORDER BY COALESCE(e.effective_from, e.hire_date) DESC, e.hire_date DESC
            ) AS row_num
        FROM staffsync_bronze.stg_employee e
        JOIN departments d 
          ON LOWER(TRIM(e.department)) = LOWER(d.department_name)
        WHERE e.employee_id IS NOT NULL
    )
    SELECT 
        employee_id, first_name, last_name, email, department_id,
        job_role, job_level, hire_date, effective_from, age,
        gender, marital_status, monthly_income, attrition
    FROM CleanedEmployees
    WHERE row_num = 1;

    -- 3. Populate Projects
    INSERT INTO projects (
        project_id, project_name, department_id, start_date, planned_end_date, status, budget
    )
    SELECT DISTINCT
        p.project_id,
        TRIM(p.project_name),
        d.department_id,
        p.start_date,
        p.planned_end_date,
        p.status,
        p.budget
    FROM staffsync_bronze.stg_project p
    JOIN departments d 
      ON LOWER(TRIM(p.department)) = LOWER(d.department_name)
    WHERE p.project_id IS NOT NULL;

    -- 4. Populate Assignments
    INSERT INTO assignments (
        assignment_id, employee_id, project_id, assigned_date, role_on_project, allocation_pct
    )
    SELECT DISTINCT
        a.assignment_id,
        a.employee_id,
        a.project_id,
        a.assigned_date,
        TRIM(a.role_on_project),
        a.allocation_pct
    FROM staffsync_bronze.stg_assignment a
    JOIN employees e ON a.employee_id = e.employee_id
    JOIN projects p ON a.project_id = p.project_id;

    -- 5. Populate Reviews
    INSERT INTO reviews (
        review_id, employee_id, project_id, review_date,
        performance_rating, review_score, job_satisfaction,
        work_life_balance, environment_satisfaction
    )
    SELECT DISTINCT
        r.review_id,
        r.employee_id,
        r.project_id,
        r.review_date,
        r.performance_rating,
        r.review_score,
        r.job_satisfaction,
        r.work_life_balance,
        r.environment_satisfaction
    FROM staffsync_bronze.stg_review r
    JOIN employees e ON r.employee_id = e.employee_id
    JOIN projects p ON r.project_id = p.project_id;

END$$

DELIMITER ;