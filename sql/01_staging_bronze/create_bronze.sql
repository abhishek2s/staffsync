SET SESSION sql_require_primary_key = 0;

CREATE DATABASE IF NOT EXISTS staffsync_bronze;
USE staffsync_bronze;

DROP TABLE IF EXISTS stg_employee;
CREATE TABLE stg_employee (
    employee_id INT,
    first_name VARCHAR(100),
    last_name VARCHAR(100),
    email VARCHAR(255),
    hire_date DATE,
    effective_from DATE,
    age INT,
    attrition VARCHAR(10),
    business_travel VARCHAR(50),
    daily_rate INT,
    department VARCHAR(100),
    distance_from_home INT,
    education INT,
    education_field VARCHAR(100),
    environment_satisfaction INT,
    gender VARCHAR(20),
    hourly_rate INT,
    job_involvement INT,
    job_level INT,
    job_role VARCHAR(100),
    job_satisfaction INT,
    marital_status VARCHAR(20),
    monthly_income INT,
    monthly_rate INT,
    num_companies_worked INT,
    over_time VARCHAR(10),
    percent_salary_hike INT,
    performance_rating INT,
    relationship_satisfaction INT,
    stock_option_level INT,
    total_working_years INT,
    training_times_last_year INT,
    work_life_balance INT,
    years_at_company INT,
    years_in_current_role INT,
    years_since_last_promotion INT,
    years_with_curr_manager INT,
    _loaded_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

DROP TABLE IF EXISTS stg_employee_history;
CREATE TABLE stg_employee_history (
    history_id INT,
    employee_id INT,
    department VARCHAR(100),
    job_role VARCHAR(100),
    job_level INT,
    monthly_income INT,
    valid_from DATE,
    valid_to DATE,
    change_reason VARCHAR(100),
    _loaded_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

DROP TABLE IF EXISTS stg_project;
CREATE TABLE stg_project (
    project_id INT,
    project_name VARCHAR(255),
    department VARCHAR(100),
    start_date DATE,
    planned_end_date DATE,
    status VARCHAR(50),
    budget DECIMAL(15, 2),
    _loaded_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

DROP TABLE IF EXISTS stg_assignment;
CREATE TABLE stg_assignment (
    assignment_id INT,
    employee_id INT,
    project_id INT,
    assigned_date DATE,
    role_on_project VARCHAR(100),
    allocation_pct INT,
    _loaded_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

DROP TABLE IF EXISTS stg_review;
CREATE TABLE stg_review (
    review_id INT,
    employee_id INT,
    project_id INT,
    review_date DATE,
    performance_rating INT,
    review_score DECIMAL(5, 2),
    job_satisfaction INT,
    work_life_balance INT,
    environment_satisfaction INT,
    _loaded_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);