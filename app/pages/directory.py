import sys
from pathlib import Path
import pandas as pd

PROJECT_ROOT = Path(__file__).resolve().parents[2]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

import streamlit as st
from src.utils.ui_helpers import setup_page
from src.dal.employee_manager import EmployeeManager
from src.dal.analytics_manager import AnalyticsManager

setup_page("Directory", "📇")

st.title("Staff Directory & Profile")
st.write("Search the active roster and view complete SCD Type 2 career histories.")
st.write("")

emp_mgr = EmployeeManager()
analytics = AnalyticsManager()

# Load departments to map the ID back to a name for the profile view
dept_df = emp_mgr.get_departments()
dept_names = {int(i): n for i, n in zip(dept_df["department_id"], dept_df["department_name"])} if not dept_df.empty else {}

# Added an explicit key and a prompt to press Enter
search = st.text_input("🔍 Search Employee Roster", placeholder="Type a name or email and press Enter...", key="dir_search_input")

if search:
    found = emp_mgr.list_employees(search=search, limit=10)
    
    if not found.empty:
        # found DataFrame contains department_name from the joined query
        labels = {int(r.employee_id): f"{r.first_name} {r.last_name} - {r.department_name}" for r in found.itertuples()}
        
        # Added an explicit key to the selectbox
        selected_id = st.selectbox("Select Profile", list(labels.keys()), format_func=lambda i: labels[i], label_visibility="collapsed", key="dir_profile_select")
        
        if selected_id:
            emp = emp_mgr.get_employee(selected_id)
            if emp:
                dept_name = dept_names.get(emp['department_id'], "Unknown Department")
                
                st.divider()
                
                # Profile Header
                st.markdown(f"## {emp['first_name']} {emp['last_name']}")
                st.caption(f"**{emp['job_role']}** • {dept_name} • {emp['email']}")
                st.write("")
                
                # Fixed Metrics (Removed the invalid 'attrition' key)
                m1, m2, m3 = st.columns(3)
                m1.metric("Job Level", emp['job_level'])
                m2.metric("Monthly Income", f"${emp['monthly_income']:,}")
                m3.metric("Hire Date", str(emp['hire_date']))
                
                st.write("")
                st.subheader("🕰️ Career Progression")
                st.caption("Historical timeline from the Gold data warehouse (SCD Type 2).")
                
                history_df = analytics.employee_history(selected_id)
                if not history_df.empty:
                    # Clean up the display of the active record
                    is_current = history_df["is_current"].astype(bool)
                    history_df["end_date"] = history_df["end_date"].astype(str).where(~is_current, "Current")
                    
                    st.dataframe(
                        history_df[["department_name", "job_role", "job_level", "monthly_income", "start_date", "end_date"]], 
                        use_container_width=True, 
                        hide_index=True
                    )
                else:
                    st.info("No historical changes recorded.")
    else:
        st.warning("No employees found matching that search.")