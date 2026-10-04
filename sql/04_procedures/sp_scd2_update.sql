-- STORED PROCEDURE: Bronze history + Silver current state -> Gold SCD Type 2

USE staffsync_gold;

DELIMITER $$

DROP PROCEDURE IF EXISTS sp_scd2_update$$

CREATE PROCEDURE sp_scd2_update()
BEGIN
    START TRANSACTION;

    DROP TEMPORARY TABLE IF EXISTS tmp_employee_versions;
    CREATE TEMPORARY TABLE tmp_employee_versions (
        employee_id INT NOT NULL,
        first_name VARCHAR(100) NOT NULL,
        last_name VARCHAR(100) NOT NULL,
        email VARCHAR(255) NOT NULL,
        department_key INT NOT NULL,
        job_role VARCHAR(100) NOT NULL,
        job_level INT NOT NULL,
        monthly_income INT NOT NULL,
        age INT NOT NULL,
        gender VARCHAR(20),
        marital_status VARCHAR(20),
        attrition VARCHAR(10),
        start_date DATE NOT NULL,
        end_date DATE NOT NULL,
        is_current BOOLEAN NOT NULL,
        change_reason VARCHAR(100)
    );

    -- Current employee versions come from the Silver OLTP snapshot.
    INSERT INTO tmp_employee_versions (
        employee_id, first_name, last_name, email, department_key,
        job_role, job_level, monthly_income, age, gender, marital_status,
        attrition, start_date, end_date, is_current, change_reason
    )
    SELECT
        e.employee_id,
        e.first_name,
        e.last_name,
        e.email,
        dd.department_key,
        e.job_role,
        e.job_level,
        e.monthly_income,
        e.age,
        e.gender,
        e.marital_status,
        e.attrition,
        COALESCE(e.effective_from, e.hire_date),
        '9999-12-31',
        TRUE,
        NULL
    FROM staffsync_silver.employees e
    JOIN staffsync_silver.departments sd
        ON sd.department_id = e.department_id
    JOIN dim_department dd
        ON dd.department_id = sd.department_id;

    -- Historical versions come from Bronze and reuse current Silver attributes
    -- for employee details not captured by the historical source.
    INSERT INTO tmp_employee_versions (
        employee_id, first_name, last_name, email, department_key,
        job_role, job_level, monthly_income, age, gender, marital_status,
        attrition, start_date, end_date, is_current, change_reason
    )
    SELECT
        h.employee_id,
        e.first_name,
        e.last_name,
        e.email,
        dd.department_key,
        TRIM(h.job_role),
        h.job_level,
        h.monthly_income,
        e.age,
        e.gender,
        e.marital_status,
        e.attrition,
        h.valid_from,
        h.valid_to,
        FALSE,
        TRIM(h.change_reason)
    FROM staffsync_bronze.stg_employee_history h
    JOIN staffsync_silver.employees e
        ON e.employee_id = h.employee_id
    JOIN staffsync_silver.departments sd
        ON LOWER(TRIM(sd.department_name)) = LOWER(TRIM(h.department))
    JOIN dim_department dd
        ON dd.department_id = sd.department_id
    WHERE h.valid_from IS NOT NULL
      AND h.valid_to IS NOT NULL
      AND h.valid_from <= h.valid_to;

    -- Close an existing current version when the current Silver snapshot
    -- represents a newer or changed version.
    UPDATE dim_employee existing_version
    JOIN tmp_employee_versions incoming_version
        ON incoming_version.employee_id = existing_version.employee_id
       AND incoming_version.is_current = TRUE
    SET existing_version.end_date = DATE_SUB(incoming_version.start_date, INTERVAL 1 DAY),
        existing_version.is_current = FALSE
    WHERE existing_version.is_current = TRUE
      AND (
          existing_version.start_date <> incoming_version.start_date
          OR existing_version.department_key <> incoming_version.department_key
          OR existing_version.job_role <> incoming_version.job_role
          OR existing_version.job_level <> incoming_version.job_level
          OR existing_version.monthly_income <> incoming_version.monthly_income
      );

    -- Insert each version only once so the procedure can be rerun safely.
    INSERT INTO dim_employee (
        employee_id, first_name, last_name, email, department_key,
        job_role, job_level, monthly_income, age, gender, marital_status,
        attrition, start_date, end_date, is_current, change_reason
    )
    SELECT
        incoming_version.employee_id,
        incoming_version.first_name,
        incoming_version.last_name,
        incoming_version.email,
        incoming_version.department_key,
        incoming_version.job_role,
        incoming_version.job_level,
        incoming_version.monthly_income,
        incoming_version.age,
        incoming_version.gender,
        incoming_version.marital_status,
        incoming_version.attrition,
        incoming_version.start_date,
        incoming_version.end_date,
        incoming_version.is_current,
        incoming_version.change_reason
    FROM tmp_employee_versions incoming_version
    WHERE NOT EXISTS (
        SELECT 1
        FROM dim_employee existing_version
        WHERE existing_version.employee_id = incoming_version.employee_id
          AND existing_version.start_date = incoming_version.start_date
          AND existing_version.end_date = incoming_version.end_date
          AND existing_version.department_key = incoming_version.department_key
          AND existing_version.job_role = incoming_version.job_role
          AND existing_version.job_level = incoming_version.job_level
          AND existing_version.monthly_income = incoming_version.monthly_income
          AND existing_version.is_current = incoming_version.is_current
    );

    DROP TEMPORARY TABLE tmp_employee_versions;
    COMMIT;
END$$

DELIMITER ;
