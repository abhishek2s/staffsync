import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[2]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from datetime import date, timedelta
import streamlit as st
from src.utils.runtime import configure_numeric_threads
from src.dal.analytics_manager import AnalyticsManager
from src.dal.employee_manager import EmployeeManager
from src.dal.project_manager import ProjectManager
from src.dal.review_manager import ReviewManager
from src.models.employee import Employee
from src.models.project import Project
from src.models.review import Review
from src.utils.ui_helpers import load_departments, setup_page, show_result

configure_numeric_threads()

setup_page("Data Entry", {"Admin"})
st.title("Data Entry")

employees = EmployeeManager()
projects = ProjectManager()
reviews = ReviewManager()
analytics = AnalyticsManager()

dept_df = load_departments()
dept_names = {int(i): n for i, n in zip(dept_df["department_id"], dept_df["department_name"])} if not dept_df.empty else {}
dept_ids = list(dept_names.keys())

tab_new, tab_update, tab_project, tab_assign, tab_review = st.tabs([
    "Onboard employee", "Update employee (SCD2)", "New project", "Assign to project", "Submit review"
])

# TAB 1: ONBOARD EMPLOYEE
with tab_new:
    st.subheader("Onboard a new employee")

    if not dept_ids:
        st.error("No departments are available. Create a department before adding an employee.")
        st.stop()
    
    with st.form("new_employee_form", clear_on_submit=True):
        c1, c2 = st.columns(2)
        first_name = c1.text_input("First name")
        last_name = c2.text_input("Last name")
        email = c1.text_input("Email")
        job_role = c2.text_input("Job role")
        
        age = c1.number_input("Age", min_value=18, max_value=70, value=30, step=1)
        monthly_income = c2.number_input("Monthly income", min_value=1, value=5000, step=100)
        
        dept_id = c1.selectbox(
            "Department",
            dept_ids,
            format_func=lambda i: dept_names[i],
        )
        job_level = c2.selectbox("Job level", [1, 2, 3, 4, 5])
        gender = c1.selectbox("Gender", ["Male", "Female", "Other"])
        marital = c2.selectbox("Marital status", ["Single", "Married", "Divorced"])
        hire_date = c1.date_input("Hire date", value=date.today(), max_value=date.today())
        
        submitted = st.form_submit_button("Add employee", type="primary")
        if submitted:
            new_employee = Employee(
                employee_id=None,
                first_name=first_name.strip(),
                last_name=last_name.strip(),
                email=email.strip().lower(),
                department_id=int(dept_id) if dept_id else 1,
                job_role=job_role.strip(),
                job_level=int(job_level),
                hire_date=hire_date,
                effective_from=hire_date,
                age=int(age),
                monthly_income=int(monthly_income),
                gender=gender,
                marital_status=marital
            )
            
            # Single source of truth validation via model
            val_error = new_employee.validate()
            if val_error:
                st.error(val_error)
            else:
                ok, message = employees.add_employee(new_employee)
                show_result(ok, message)
                if ok:
                    st.rerun()

# TAB 2: UPDATE EMPLOYEE (SCD TYPE 2 & OFFBOARDING)
with tab_update:
    st.subheader("Update Employee Profile or Offboard Staff")
    st.caption("Select an employee to edit their profile or mark them as departed. Saving creates a NEW history version in Gold (SCD Type 2).")

    emp_df = employees.list_employees(limit=1000)

    if emp_df is None or emp_df.empty:
        st.info("No employees found in the database.")
    else:
        emp_options = {
            int(row.employee_id): f"{row.first_name} {row.last_name} ({row.email})"
            for row in emp_df.itertuples()
        }

        selected_emp_id = st.selectbox(
            "Search & Select Employee",
            options=list(emp_options.keys()),
            format_func=lambda x: emp_options[x],
            index=0,
            key="single_upd_emp_select"
        )

        current = employees.get_employee(selected_emp_id)
        if current:
            current_attrition = current.get("attrition", "No")

            st.info(
                f"**Current Version (Effective {current['effective_from']}):** "
                f"Dept: {dept_names.get(current['department_id'], '?')} | "
                f"Role: {current['job_role']} | "
                f"Level: {current['job_level']} | "
                f"Income: ₹{current['monthly_income']:,} | "
                f"Attrition: {current_attrition}"
            )

            with st.form(f"update_employee_form_{selected_emp_id}"):
                c1, c2 = st.columns(2)
                
                dept_index = dept_ids.index(current["department_id"]) if current["department_id"] in dept_ids else 0
                new_dept = c1.selectbox("Department", dept_ids, index=dept_index, format_func=lambda i: dept_names[i], key=f"dept_{selected_emp_id}")
                new_role = c2.text_input("Job role", value=current["job_role"], key=f"role_{selected_emp_id}")
                
                level_index = min(max(int(current["job_level"]), 1), 5) - 1
                new_level = c1.selectbox("Job level", [1, 2, 3, 4, 5], index=level_index, key=f"level_{selected_emp_id}")
                new_income = c2.number_input("Monthly income", min_value=1, value=int(current["monthly_income"]), step=100, key=f"income_{selected_emp_id}")
                
                attr_index = 0 if current_attrition == "No" else 1
                new_attrition = c1.selectbox(
                    "Attrition Status (Mark Departed)",
                    ["No", "Yes"],
                    index=attr_index,
                    help="Set to 'Yes' to offboard this employee. Preserves history in Gold.",
                    key=f"attr_{selected_emp_id}"
                )
                
                save = st.form_submit_button("Save changes", type="primary")
                if save:
                    ok, message = employees.update_employee(
                        selected_emp_id, 
                        int(new_dept), 
                        new_role.strip(), 
                        int(new_level), 
                        int(new_income),
                        new_attrition
                    )
                    show_result(ok, message)
                    if ok:
                        st.rerun()

            st.write("**History of this employee in the warehouse**")
            history = analytics.employee_history(selected_emp_id)
            if history is not None and not history.empty:
                history["end_date"] = history["end_date"].astype(str)
                st.dataframe(history, hide_index=True, use_container_width=True)

# TAB 3: NEW PROJECT & STATUS UPDATE
with tab_project:
    st.subheader("Create a project")
    
    with st.form("new_project_form", clear_on_submit=True):
        col1, col2 = st.columns(2)
        
        proj_name = col1.text_input("Project name")
        project_dept = col2.selectbox(
            "Department", 
            dept_ids, 
            format_func=lambda i: dept_names[i]
        ) if dept_ids else col2.text_input("Department ID")
        
        start = col1.date_input("Start date", value=date.today())
        end = col2.date_input("Planned end date", value=date.today() + timedelta(days=90))

        existing = projects.list_projects(limit=1000)
        statuses = sorted(set(existing["status"].dropna()) if (existing is not None and not existing.empty) else {"Planned", "Active", "Completed", "On Hold"})
        status = col1.selectbox("Status", statuses)
        budget = col2.number_input("Budget", min_value=0.0, value=50000.0, step=1000.0)
        
        submitted = st.form_submit_button("Create project", type="primary")
        if submitted:
            project = Project(
                None, proj_name.strip(), int(project_dept) if project_dept else 1,
                start, end, status, float(budget)
            )
            # Model validation
            val_error = project.validate()
            if val_error:
                st.error(val_error)
            else:
                ok, message = projects.add_project(project)
                show_result(ok, message)
                if ok:
                    st.rerun()

    st.markdown("---")
    st.subheader("Update Project Status")
    st.caption("Select a project to update its lifecycle status.")

    proj_df = projects.list_projects(limit=1000)
    if proj_df is None or proj_df.empty:
        st.info("No projects found.")
    else:
        proj_options = {
            int(row.project_id): f"{row.project_name} (ID: {row.project_id} | Status: {row.status})"
            for row in proj_df.itertuples()
        }

        selected_proj_id = st.selectbox(
            "Search & Select Project",
            options=list(proj_options.keys()),
            format_func=lambda x: proj_options[x],
            key="upd_proj_status_select"
        )

        current_proj = proj_df[proj_df["project_id"] == selected_proj_id].iloc[0]

        with st.form(f"update_project_status_form_{selected_proj_id}"):
            c1, c2 = st.columns(2)
            c1.text_input("Project Name", value=current_proj["project_name"], disabled=True)
            c2.text_input("Current Status", value=current_proj["status"], disabled=True)

            status_list = ["Planned", "Active", "Completed", "On Hold"]
            current_status_idx = status_list.index(current_proj["status"]) if current_proj["status"] in status_list else 0
            
            new_proj_status = c1.selectbox(
                "New Status",
                options=status_list,
                index=current_status_idx,
                key=f"new_status_{selected_proj_id}"
            )

            update_status_btn = st.form_submit_button("Update Project Status", type="primary")
            if update_status_btn:
                ok, message = projects.update_project_status(selected_proj_id, new_proj_status)
                show_result(ok, message)
                if ok:
                    st.rerun()

    st.markdown("---")
    st.write("**Most recent projects**")
    recent_projs = projects.list_projects(limit=10)
    if recent_projs is not None and not recent_projs.empty:
        st.dataframe(recent_projs, hide_index=True)

# TAB 4: ASSIGN TO PROJECT
with tab_assign:
    st.subheader("Assign an employee to a project")

    emp_df = employees.list_employees(limit=1000)
    proj_df = projects.list_projects(limit=1000)

    if emp_df is None or proj_df is None or emp_df.empty or proj_df.empty:
        st.info("Ensure you have at least one employee and one project created.")
    else:
        emp_options = {
            int(r.employee_id): f"{r.first_name} {r.last_name} ({r.email})"
            for r in emp_df.itertuples()
        }
        proj_options = {
            int(r.project_id): f"{r.project_name} (ID: {r.project_id})"
            for r in proj_df.itertuples()
        }

        c1, c2 = st.columns(2)
        sel_emp_id = c1.selectbox("Search & Select Employee", options=list(emp_options.keys()), format_func=lambda x: emp_options[x], key="asg_emp_sel")
        sel_proj_id = c2.selectbox("Search & Select Project", options=list(proj_options.keys()), format_func=lambda x: proj_options[x], key="asg_proj_sel")

        with st.form("assign_form"):
            role_on_project = st.text_input("Role on project", value="Contributor")
            allocation = st.slider("Allocation (%)", min_value=1, max_value=100, value=25)
            
            submitted = st.form_submit_button("Assign Employee", type="primary")
            if submitted:
                ok, message = projects.assign_employee(sel_emp_id, sel_proj_id, role_on_project.strip(), allocation)
                show_result(ok, message)
                if ok:
                    st.rerun()
                
        st.write("**People currently on this project**")
        assignments = projects.list_assignments(project_id=sel_proj_id)
        if assignments is not None and not assignments.empty:
            st.dataframe(assignments, hide_index=True)

# TAB 5: SUBMIT REVIEW
with tab_review:
    st.subheader("Submit a performance review")

    emp_df = employees.list_employees(limit=1000)

    if emp_df is None or emp_df.empty:
        st.info("No employees found in the database.")
    else:
        emp_options = {
            int(r.employee_id): f"{r.first_name} {r.last_name} ({r.email})"
            for r in emp_df.itertuples()
        }

        sel_rev_emp_id = st.selectbox(
            "Search & Select Employee",
            options=list(emp_options.keys()),
            format_func=lambda x: emp_options[x],
            key="rev_emp_sel"
        )

        assigned_projs = projects.list_employee_projects(sel_rev_emp_id, limit=200)

        if assigned_projs is None or assigned_projs.empty:
            st.warning("This employee is not currently assigned to any active projects. Assign them to a project first before submitting a review.")
        else:
            assigned_options = {
                int(r.project_id): f"{r.project_name} (ID: {r.project_id})"
                for r in assigned_projs.itertuples()
            }

            sel_rev_proj_id = st.selectbox(
                "Select Assigned Project",
                options=list(assigned_options.keys()),
                format_func=lambda x: assigned_options[x],
                key=f"rev_proj_sel_{sel_rev_emp_id}"
            )

            with st.form(f"review_form_{sel_rev_emp_id}_{sel_rev_proj_id}"):
                c1, c2 = st.columns(2)
                review_date = c1.date_input("Review date", value=date.today(), max_value=date.today())
                rating = c2.select_slider("Performance rating (1 = low, 4 = outstanding)", options=[1, 2, 3, 4], value=3)
                score = c1.slider("Review score", min_value=0.0, max_value=100.0, value=75.0, step=0.5)
                job_sat = c2.select_slider("Job satisfaction", options=[1, 2, 3, 4], value=3)
                wlb = c1.select_slider("Work-life balance", options=[1, 2, 3, 4], value=3)
                env_sat = c2.select_slider("Environment satisfaction", options=[1, 2, 3, 4], value=3)
                
                submitted = st.form_submit_button("Submit review", type="primary")
                if submitted:
                    review = Review(
                        None, 
                        int(sel_rev_emp_id), 
                        int(sel_rev_proj_id), 
                        review_date, 
                        int(rating), 
                        float(score), 
                        int(job_sat), 
                        int(wlb), 
                        int(env_sat)
                    )
                    # Model validation
                    val_error = review.validate()
                    if val_error:
                        st.error(val_error)
                    else:
                        ok, message = reviews.add_review(review)
                        show_result(ok, message)
                        if ok:
                            st.rerun()
                    
            st.write("**Recent reviews for this employee**")
            rev_list = reviews.list_reviews(employee_id=sel_rev_emp_id, limit=10)
            if rev_list is not None and not rev_list.empty:
                st.dataframe(rev_list, hide_index=True)