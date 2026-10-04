import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[2]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from datetime import date, timedelta
import re
import streamlit as st
from src.dal.analytics_manager import AnalyticsManager
from src.dal.employee_manager import EmployeeManager
from src.dal.project_manager import ProjectManager
from src.dal.review_manager import ReviewManager
from src.models.employee import Employee
from src.models.project import Project
from src.models.review import Review
from src.utils.ui_helpers import load_departments, setup_page, show_result

setup_page("Data Entry")
st.title("Data Entry")

employees = EmployeeManager()
projects = ProjectManager()
reviews = ReviewManager()
analytics = AnalyticsManager()

dept_df = load_departments()
dept_names = {int(i): n for i, n in zip(dept_df["department_id"], dept_df["department_name"])}
dept_ids = list(dept_names.keys())


def pick_employee(key):
    search = st.text_input(
        "Search employee by name or email",
        key=f"{key}_employee_search",
        placeholder="Type a name or email address",
    ).strip()
    if not search:
        st.caption("Start typing to search for an employee.")
        return None
    if not re.search(r"[A-Za-z@]", search):
        st.info("Please search using an employee name or email address.")
        return None

    found = employees.list_employees(search=search, limit=25)
    if found.empty:
        st.info("No employees match your search.")
        return None
    labels = {
        int(r.employee_id): f"{r.first_name} {r.last_name} ({r.email})"
        for r in found.itertuples()
    }
    return st.selectbox(
        "Select employee",
        list(labels.keys()),
        format_func=lambda employee_id: labels[employee_id],
        index=None,
        key=f"{key}_emp_pick_{search}",
    )

def pick_project(key):
    search = st.text_input(
        "Search project by ID or name",
        key=f"{key}_project_search",
        placeholder="Type a project ID or name",
    ).strip()
    if not search:
        st.caption("Start typing to search for a project.")
        return None

    found = projects.list_projects(search=search, limit=25)
    if found.empty:
        st.info("No projects match your search.")
        return None
    labels = {
        int(r.project_id): f"{r.project_name} (ID: {r.project_id})"
        for r in found.itertuples()
    }
    return st.selectbox(
        "Select project",
        list(labels.keys()),
        format_func=lambda project_id: labels[project_id],
        index=None,
        placeholder="Select a project from the search results",
        key=f"{key}_proj_pick_{search}",
    )


def pick_assigned_project(key, employee_id):
    if employee_id is None:
        st.caption("Select an employee first to see assigned projects.")
        return None

    found = projects.list_employee_projects(employee_id, limit=200)
    if found.empty:
        st.info("This employee has no assigned projects.")
        return None

    labels = {
        int(r.project_id): f"{r.project_name} (ID: {r.project_id})"
        for r in found.itertuples()
    }
    return st.selectbox(
        "Select assigned project",
        list(labels.keys()),
        format_func=lambda project_id: labels[project_id],
        index=None,
        placeholder="Choose a project assigned to this employee",
        key=f"{key}_assigned_project_{employee_id}",
    )


FIELD_RULES = {
    "new_first_name": (r"[A-Za-z]+(?:[ '-][A-Za-z]+)*", "First name is invalid."),
    "new_last_name": (r"[A-Za-z]+(?:[ '-][A-Za-z]+)*", "Last name is invalid."),
    "new_email": (r"[A-Za-z0-9._%+-]+@[A-Za-z0-9-]+(?:\.[A-Za-z]{2,})", "Email is invalid."),
    "new_job_role": (r"[A-Za-z]+(?:[ '&/-][A-Za-z]+)*", "Job role is invalid."),
}
PROJECT_FIELD_RULES = {
    "new_project_name": (
        r"(?=.*[A-Za-z])[A-Za-z0-9][A-Za-z0-9 '&/_().-]*",
        "Project name is invalid. Please include at least one letter.",
    ),
}

NUMBER_RULES = {
    "new_age": (18, 70, "Age must be between 18 and 70."),
    "new_income": (1, None, "Monthly income must be greater than 0."),
}


def update_field_state(key):
    text_rules = {**FIELD_RULES, **PROJECT_FIELD_RULES}
    if key in text_rules:
        pattern, _ = text_rules[key]
        value = st.session_state.get(key, "").strip()
        st.session_state[f"{key}_invalid"] = not bool(re.fullmatch(pattern, value))
        return

    minimum, maximum, _ = NUMBER_RULES[key]
    value = st.session_state.get(key)
    st.session_state[f"{key}_invalid"] = (
        value is None or value < minimum or (maximum is not None and value > maximum)
    )


def render_text_input(column, label, key):
    column.text_input(label, key=key, on_change=update_field_state, args=(key,))
    if st.session_state.get(f"{key}_invalid", False):
        rules = {**FIELD_RULES, **PROJECT_FIELD_RULES}
        column.error(rules[key][1])


def render_number_input(column, label, key, **kwargs):
    column.number_input(label, key=key, on_change=update_field_state, args=(key,), **kwargs)
    if st.session_state.get(f"{key}_invalid", False):
        column.error(NUMBER_RULES[key][2])


def update_project_date_state():
    start = st.session_state.get("new_project_start")
    end = st.session_state.get("new_project_end")
    invalid = start is not None and end is not None and end <= start
    st.session_state.new_project_dates_invalid = invalid


def show_invalid_field_styles(extra_fields=None, date_fields=None):
    extra_fields = extra_fields or {}
    date_fields = date_fields or {}
    invalid_text_labels = [
        label for key, label in (
            ("new_first_name", "First name"),
            ("new_last_name", "Last name"),
            ("new_email", "Email"),
            ("new_job_role", "Job role"),
        )
        if st.session_state.get(f"{key}_invalid", False)
    ] + [
        label for key, label in extra_fields.items()
        if st.session_state.get(f"{key}_invalid", False)
    ]
    invalid_number_labels = [
        label for key, label in (
            ("new_age", "Age"),
            ("new_income", "Monthly income"),
        )
        if st.session_state.get(f"{key}_invalid", False)
    ]
    selectors = [
            f'div[data-testid="stTextInput"]:has(input[aria-label="{label}"]) '
            'div[data-testid="stTextInputRootElement"]'
            for label in invalid_text_labels
        ] + [
            f'div[data-testid="stNumberInput"]:has(input[aria-label="{label}"]) '
            'div[data-testid="stNumberInputContainer"]'
            for label in invalid_number_labels
        ] + [
            f'div[data-testid="stDateInput"]:has(input[aria-label*="{label}"])'
            for key, label in date_fields.items()
            if st.session_state.get(f"{key}_invalid", False)
        ]
    if selectors:
        st.markdown(
            f"""
            <style>
            {", ".join(selectors)} {{
                border: 1px solid #ff4b4b !important;
                background-color: rgba(255, 75, 75, 0.15) !important;
                box-shadow: 0 0 0 1px #ff4b4b !important;
            }}
            </style>
            """,
            unsafe_allow_html=True,
        )


if st.session_state.pop("clear_new_employee_fields", False):
    for field_key in FIELD_RULES:
        st.session_state[field_key] = ""
        st.session_state[f"{field_key}_invalid"] = False
    st.session_state.new_age = 30
    st.session_state.new_income = 5000
    for field_key in NUMBER_RULES:
        st.session_state[f"{field_key}_invalid"] = False
    st.session_state.new_project_name = ""
    st.session_state.new_project_name_invalid = False


tab_new, tab_update, tab_project, tab_assign, tab_review = st.tabs([
    "Onboard employee", "Update employee (SCD2)", "New project", "Assign to project", "Submit review"
])

# TAB 1: ONBOARD EMPLOYEE
with tab_new:
    st.subheader("Onboard a new employee")
    c1, c2 = st.columns(2)
    render_text_input(c1, "First name", "new_first_name")
    render_text_input(c2, "Last name", "new_last_name")
    render_text_input(c1, "Email", "new_email")
    render_text_input(c2, "Job role", "new_job_role")
    c1, c2 = st.columns(2)
    render_number_input(c1, "Age", "new_age", min_value=-999999, max_value=150, value=30)
    render_number_input(c2, "Monthly income", "new_income", min_value=-999999999, value=5000, step=100)
    show_invalid_field_styles()
    with st.form("new_employee_form", clear_on_submit=True):
        c1, c2 = st.columns(2)
        dept_id = c1.selectbox("Department", dept_ids, format_func=lambda i: dept_names[i])
        job_level = c2.selectbox("Job level", [1, 2, 3, 4, 5])
        gender = c1.selectbox("Gender", ["Male", "Female", "Other"])
        marital = c2.selectbox("Marital status", ["Single", "Married", "Divorced"])
        hire_date = c1.date_input("Hire date", value=date.today(), max_value=date.today())
        
        submitted = st.form_submit_button("Add employee", type="primary")
        if submitted:
            for key in FIELD_RULES:
                update_field_state(key)
            for key in NUMBER_RULES:
                update_field_state(key)
            field_errors = [
                message for key, (_, message) in {**FIELD_RULES, **NUMBER_RULES}.items()
                if st.session_state.get(f"{key}_invalid", False)
            ]
            if field_errors:
                for message in field_errors:
                    st.error(message)
                st.rerun()

            new_employee = Employee(
                employee_id=None, first_name=st.session_state.new_first_name,
                last_name=st.session_state.new_last_name,
                email=st.session_state.new_email.strip().lower(),
                department_id=int(dept_id), job_role=st.session_state.new_job_role.strip(),
                job_level=int(job_level), hire_date=hire_date, effective_from=hire_date,
                age=int(st.session_state.new_age),
                monthly_income=int(st.session_state.new_income),
                gender=gender, marital_status=marital
            )
            ok, message = employees.add_employee(new_employee)
            show_result(ok, message)
            if ok:
                st.session_state.clear_new_employee_fields = True
                st.rerun()

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
    with st.container(border=True):
        project_name_column, _ = st.columns(2)
        render_text_input(project_name_column, "Project name", "new_project_name")
        date_columns = st.columns(2)
        start = date_columns[0].date_input(
            "Start date",
            value=date.today(),
            key="new_project_start",
            on_change=update_project_date_state,
        )
        end = date_columns[1].date_input(
            "Planned end date",
            value=date.today() + timedelta(days=90),
            key="new_project_end",
            on_change=update_project_date_state,
        )
        if st.session_state.get("new_project_dates_invalid", False):
            date_columns[1].error("Planned end date must be after the start date.")
        show_invalid_field_styles(
            {"new_project_name": "Project name"},
            {"new_project_start": "Start date", "new_project_end": "Planned end date"},
        )

        with st.form("new_project_form", clear_on_submit=True, border=False):
            c1, c2 = st.columns(2)
            project_dept = c2.selectbox("Department", dept_ids, format_func=lambda i: dept_names[i], key="proj_dept")
            status = c1.selectbox("Status", statuses)
            budget = c2.number_input("Budget", min_value=0.0, value=50000.0, step=1000.0)
            
            submitted = st.form_submit_button("Create project", type="primary")
            if submitted:
                update_field_state("new_project_name")
                update_project_date_state()
                if st.session_state.new_project_name_invalid:
                    st.rerun()
                if st.session_state.new_project_dates_invalid:
                    st.rerun()
                if end <= start:
                    st.stop()

                project = Project(
                    None, st.session_state.new_project_name, int(project_dept),
                    start, end, status, float(budget),
                )
                ok, message = projects.add_project(project)
                show_result(ok, message)
                if ok:
                    st.session_state.new_project_name = ""
                    st.session_state.new_project_name_invalid = False
                    st.rerun()
            
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
    r_proj = pick_assigned_project("rev", r_emp)
    
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