-- GOLD LAYER: Dimensional OLAP Data Warehouse

CREATE DATABASE IF NOT EXISTS staffsync_gold;
USE staffsync_gold;

DROP TABLE IF EXISTS fact_performance_reviews;
DROP TABLE IF EXISTS dim_employee;
DROP TABLE IF EXISTS dim_project;
DROP TABLE IF EXISTS dim_date;
DROP TABLE IF EXISTS dim_department;

-- 1. Department Dimension
CREATE TABLE dim_department (
    department_key INT AUTO_INCREMENT PRIMARY KEY,
    department_id INT NOT NULL,
    department_name VARCHAR(100) NOT NULL,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    CONSTRAINT uq_dim_department_business_key UNIQUE (department_id),
    CONSTRAINT uq_dim_department_name UNIQUE (department_name)
);

-- 2. Date Dimension
CREATE TABLE dim_date (
    date_key INT PRIMARY KEY,
    full_date DATE NOT NULL,
    day_of_month TINYINT NOT NULL,
    month_number TINYINT NOT NULL,
    month_name VARCHAR(20) NOT NULL,
    quarter_number TINYINT NOT NULL,
    year_number SMALLINT NOT NULL,
    week_number TINYINT NOT NULL,
    day_name VARCHAR(20) NOT NULL,
    CONSTRAINT uq_dim_date_full_date UNIQUE (full_date)
);

-- 3. Project Dimension
CREATE TABLE dim_project (
    project_key BIGINT AUTO_INCREMENT PRIMARY KEY,
    project_id INT NOT NULL,
    project_name VARCHAR(255) NOT NULL,
    department_key INT NOT NULL,
    project_start_date DATE NOT NULL,
    planned_end_date DATE NOT NULL,
    status VARCHAR(50) NOT NULL,
    budget DECIMAL(15, 2) NOT NULL,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    CONSTRAINT uq_dim_project_business_key UNIQUE (project_id),
    CONSTRAINT fk_dim_project_department FOREIGN KEY (department_key)
        REFERENCES dim_department(department_key)
);

-- 4. Employee Dimension (SCD Type 2)
CREATE TABLE dim_employee (
    employee_key BIGINT AUTO_INCREMENT PRIMARY KEY,
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
    is_current BOOLEAN NOT NULL DEFAULT TRUE,
    change_reason VARCHAR(100),
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    CONSTRAINT fk_dim_employee_department FOREIGN KEY (department_key)
        REFERENCES dim_department(department_key),
    INDEX ix_dim_employee_business_key (employee_id),
    INDEX ix_dim_employee_current (employee_id, is_current),
    INDEX ix_dim_employee_validity (employee_id, start_date, end_date)
);

-- 5. Performance Review Fact Table
CREATE TABLE fact_performance_reviews (
    performance_review_key BIGINT AUTO_INCREMENT PRIMARY KEY,
    review_id INT NOT NULL,
    employee_key BIGINT NOT NULL,
    project_key BIGINT NOT NULL,
    date_key INT NOT NULL,
    department_key INT NOT NULL,
    performance_rating INT NOT NULL,
    review_score DECIMAL(5, 2) NOT NULL,
    job_satisfaction INT,
    work_life_balance INT,
    environment_satisfaction INT,
    review_count TINYINT NOT NULL DEFAULT 1,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    CONSTRAINT uq_fact_review_business_key UNIQUE (review_id),
    CONSTRAINT fk_fact_employee FOREIGN KEY (employee_key)
        REFERENCES dim_employee(employee_key),
    CONSTRAINT fk_fact_project FOREIGN KEY (project_key)
        REFERENCES dim_project(project_key),
    CONSTRAINT fk_fact_date FOREIGN KEY (date_key)
        REFERENCES dim_date(date_key),
    CONSTRAINT fk_fact_department FOREIGN KEY (department_key)
        REFERENCES dim_department(department_key),
    INDEX ix_fact_employee (employee_key),
    INDEX ix_fact_project (project_key),
    INDEX ix_fact_date (date_key),
    INDEX ix_fact_department (department_key)
);
