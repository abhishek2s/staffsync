-- ============================================================================
-- SILVER LAYER: 3NF Relational Operational Database (OLTP)
-- Database: staffsync_silver
-- ============================================================================
CREATE DATABASE IF NOT EXISTS staffsync_silver;
USE staffsync_silver;

-- 1. Departments Table (Extracted Lookup Entity)
DROP TABLE IF EXISTS reviews;
DROP TABLE IF EXISTS assignments;
DROP TABLE IF EXISTS projects;
DROP TABLE IF EXISTS employees;
DROP TABLE IF EXISTS departments;

CREATE TABLE departments (
    department_id INT AUTO_INCREMENT PRIMARY KEY,
    department_name VARCHAR(100) NOT NULL UNIQUE,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- 2. Employees Table
CREATE TABLE employees (
    employee_id INT PRIMARY KEY,
    first_name VARCHAR(100) NOT NULL,
    last_name VARCHAR(100) NOT NULL,
    email VARCHAR(255) NOT NULL UNIQUE,
    department_id INT NOT NULL,
    job_role VARCHAR(100) NOT NULL,
    job_level INT NOT NULL,
    hire_date DATE NOT NULL,
    effective_from DATE NOT NULL,
    age INT NOT NULL,
    gender VARCHAR(20),
    marital_status VARCHAR(20),
    monthly_income INT NOT NULL,
    attrition VARCHAR(10),
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    CONSTRAINT fk_emp_dept FOREIGN KEY (department_id) 
        REFERENCES departments(department_id) ON DELETE RESTRICT
);

-- 3. Projects Table
CREATE TABLE projects (
    project_id INT PRIMARY KEY,
    project_name VARCHAR(255) NOT NULL,
    department_id INT NOT NULL,
    start_date DATE NOT NULL,
    planned_end_date DATE NOT NULL,
    status VARCHAR(50) NOT NULL,
    budget DECIMAL(15, 2) NOT NULL,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    CONSTRAINT fk_proj_dept FOREIGN KEY (department_id) 
        REFERENCES departments(department_id) ON DELETE RESTRICT
);

-- 4. Assignments Table (Junction / Operational Transaction)
CREATE TABLE assignments (
    assignment_id INT PRIMARY KEY,
    employee_id INT NOT NULL,
    project_id INT NOT NULL,
    assigned_date DATE NOT NULL,
    role_on_project VARCHAR(100) NOT NULL,
    allocation_pct INT NOT NULL,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    CONSTRAINT fk_asgn_emp FOREIGN KEY (employee_id) 
        REFERENCES employees(employee_id) ON DELETE CASCADE,
    CONSTRAINT fk_asgn_proj FOREIGN KEY (project_id) 
        REFERENCES projects(project_id) ON DELETE CASCADE
);

-- 5. Reviews Table
CREATE TABLE reviews (
    review_id INT PRIMARY KEY,
    employee_id INT NOT NULL,
    project_id INT NOT NULL,
    review_date DATE NOT NULL,
    performance_rating INT NOT NULL,
    review_score DECIMAL(5, 2) NOT NULL,
    job_satisfaction INT,
    work_life_balance INT,
    environment_satisfaction INT,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    CONSTRAINT fk_rev_emp FOREIGN KEY (employee_id) 
        REFERENCES employees(employee_id) ON DELETE CASCADE,
    CONSTRAINT fk_rev_proj FOREIGN KEY (project_id) 
        REFERENCES projects(project_id) ON DELETE CASCADE
);