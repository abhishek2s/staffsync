import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[2]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from datetime import date, timedelta
import streamlit as st
from src.dal.analytics_manager import AnalyticsManager
from src.dal.employee_manager import EmployeeManager
from src.dal.project_manager import ProjectManager
from src.dal.review_manager import ReviewManager
from src.models.employee import Employee
from src.models.project import Project
from src.models.review import Review
from src.utils.ui_helpers import load_departments, setup_page, show_result

setup_page("Data Entry", "")
st.title("Data Entry")

employees = EmployeeManager()
projects = ProjectManager()
reviews = ReviewManager()
analytics = AnalyticsManager()

dept_df = load_departments()
dept_names = {int(i): n for i, n in zip(dept_df["department_id"], dept_df["department_name"])}
dept_ids = list(dept_names.keys())

def pick_employee(key):
    search = st.text_input("Search employee by name or email", key=f"{key}_search")
    found = employees.list_employees(search=search or None, limit=25)
    if found.empty:
        st.info("No employees match your search.")
        return None
    labels = {int(r.employee_id): f"{r.employee_id} {r.first_name} {r.last_name} ({r.department_name})" for r in found.itertuples()}
    return st.selectbox("Select employee", list(labels.keys()), format_func=lambda i: labels[i], key=f"{key}_emp_pick")

def pick_project(key):
    found = projects.list_projects(limit=500)
    if found.empty:
        st.info("There are no projects yet. Create one in the 'New project' tab.")
        return None
    labels = {int(r.project_id): f"{r.project_id} {r.project_name}" for r in found.itertuples()}
    return st.selectbox("Select project", list(labels.keys()), format_func=lambda i: labels[i], key=f"{key}_proj_pick")

tab_new, tab_update, tab_project, tab_assign, tab_review = st.tabs([
    "Onboard employee", "Update employee (SCD2)", "New project", "Assign to project", "Submit review"
])

# TAB 1: ONBOARD EMPLOYEE
with tab_new:
    st.subheader("Onboard a new employee")
    with st.form("new_employee_form", clear_on_submit=True):
        c1, c2 = st.columns(2)
        first_name = c1.text_input("First name")
        last_name = c2.text_input("Last name")
        email = c1.text_input("Email")
        job_role = c2.text_input("Job role")
        dept_id = c1.selectbox("Department", dept_ids, format_func=lambda i: dept_names[i])
        job_level = c2.selectbox("Job level", [1, 2, 3, 4, 5])
        age = c1.number_input("Age", min_value=18, max_value=70, value=30)
        income = c2.number_input("Monthly income", min_value=1, value=5000, step=100)
        gender = c1.selectbox("Gender", ["Male", "Female", "Other"])
        marital = c2.selectbox("Marital status", ["Single", "Married", "Divorced"])
        hire_date = c1.date_input("Hire date", value=date.today(), max_value=date.today())
        
        submitted = st.form_submit_button("Add employee", type="primary")
        if submitted:
            new_employee = Employee(
                employee_id=None, first_name=first_name, last_name=last_name,
                email=email.strip().lower(), department_id=int(dept_id), job_role=job_role.strip(),
                job_level=int(job_level), hire_date=hire_date, effective_from=hire_date, age=int(age),
                monthly_income=int(income), gender=gender, marital_status=marital
            )
            ok, message = employees.add_employee(new_employee)
            show_result(ok, message)

# TAB 2: UPDATE EMPLOYEE (SCD TYPE 2)
with tab_update:
    st.subheader("Change an employee's department, role, level or salary")
    st.caption("Saving creates a NEW history version in the data warehouse (SCD Type 2). The old row is closed and a new current row is opened. Tip: an employee can only be changed once per day, and not on their hire date.")
    emp_id = pick_employee("upd")
    
    if emp_id is not None:
        current = employees.get_employee(emp_id)
        st.info(f"Current version started on {current['effective_from']}: {dept_names.get(current['department_id'], '?')}, {current['job_role']}, level {current['job_level']}, income {current['monthly_income']:,}")
        
        with st.form("update_employee_form"):
            c1, c2 = st.columns(2)
            dept_index = dept_ids.index(current["department_id"]) if current["department_id"] in dept_ids else 0
            new_dept = c1.selectbox("Department", dept_ids, index=dept_index, format_func=lambda i: dept_names[i], key=f"dept_{emp_id}")
            new_role = c2.text_input("Job role", value=current["job_role"], key=f"role_{emp_id}")
            level_index = min(max(int(current["job_level"]), 1), 5) - 1
            new_level = c1.selectbox("Job level", [1, 2, 3, 4, 5], index=level_index, key=f"level_{emp_id}")
            new_income = c2.number_input("Monthly income", min_value=1, value=int(current["monthly_income"]), step=100, key=f"income_{emp_id}")
            
            save = st.form_submit_button("Save changes", type="primary")
            if save:
                ok, message = employees.update_employee(emp_id, int(new_dept), new_role, int(new_level), int(new_income))
                show_result(ok, message)
                
        st.write("**History of this employee in the warehouse**")
        history = analytics.employee_history(emp_id)
        if not history.empty:
            history["end_date"] = history["end_date"].astype(str)
            st.dataframe(history, hide_index=True)

# TAB 3: NEW PROJECT
with tab_project:
    st.subheader("Create a project")
    existing = projects.list_projects(limit=1000)
    statuses = sorted(set(existing["status"].dropna()) | {"Planned", "Active", "Completed"})
    
    with st.form("new_project_form", clear_on_submit=True):
        c1, c2 = st.columns(2)
        project_name = c1.text_input("Project name")
        project_dept = c2.selectbox("Department", dept_ids, format_func=lambda i: dept_names[i], key="proj_dept")
        status = c1.selectbox("Status", statuses)
        budget = c2.number_input("Budget", min_value=0.0, value=50000.0, step=1000.0)
        start = c1.date_input("Start date", value=date.today())
        end = c2.date_input("Planned end date", value=date.today() + timedelta(days=90))
        
        submitted = st.form_submit_button("Create project", type="primary")
        if submitted:
            project = Project(None, project_name, int(project_dept), start, end, status, float(budget))
            ok, message = projects.add_project(project)
            show_result(ok, message)
            
    st.write("**Most recent projects**")
    st.dataframe(projects.list_projects(limit=10), hide_index=True)

# TAB 4: ASSIGN TO PROJECT
with tab_assign:
    st.subheader("Assign an employee to a project")
    a_emp = pick_employee("asg")
    a_proj = pick_project("asg")
    
    if a_emp is not None and a_proj is not None:
        with st.form("assign_form"):
            role_on_project = st.text_input("Role on project", value="Contributor")
            allocation = st.slider("Allocation (%)", min_value=1, max_value=100, value=25)
            
            submitted = st.form_submit_button("Assign", type="primary")
            if submitted:
                ok, message = projects.assign_employee(a_emp, a_proj, role_on_project, allocation)
                show_result(ok, message)
                
        st.write("**People currently on this project**")
        st.dataframe(projects.list_assignments(project_id=a_proj), hide_index=True)

# TAB 5: SUBMIT REVIEW
with tab_review:
    st.subheader("Submit a performance review")
    r_emp = pick_employee("rev")
    r_proj = pick_project("rev")
    
    if r_emp is not None and r_proj is not None:
        with st.form("review_form"):
            c1, c2 = st.columns(2)
            review_date = c1.date_input("Review date", value=date.today(), max_value=date.today())
            rating = c2.select_slider("Performance rating (1 = low, 4 = outstanding)", options=[1, 2, 3, 4], value=3)
            score = c1.slider("Review score", min_value=0.0, max_value=100.0, value=75.0, step=0.5)
            job_sat = c2.select_slider("Job satisfaction", options=[1, 2, 3, 4], value=3)
            wlb = c1.select_slider("Work-life balance", options=[1, 2, 3, 4], value=3)
            env_sat = c2.select_slider("Environment satisfaction", options=[1, 2, 3, 4], value=3)
            
            submitted = st.form_submit_button("Submit review", type="primary")
            if submitted:
                review = Review(None, int(r_emp), int(r_proj), review_date, int(rating), float(score), int(job_sat), int(wlb), int(env_sat))
                ok, message = reviews.add_review(review)
                show_result(ok, message)
                
        st.write("**Recent reviews for this employee**")
        st.dataframe(reviews.list_reviews(employee_id=r_emp, limit=10), hide_index=True)