import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[2]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from datetime import date
import pandas as pd
import plotly.express as px
import streamlit as st
from src.utils.ui_helpers import get_data, setup_page

setup_page("Analytics")
st.title("Analytics Dashboard")

kpis = get_data("get_kpis")
if kpis is None:
    st.stop()

# KPI row
k = st.columns(5)
k[0].metric("Employees", f"{kpis['total_employees']:,}")
k[1].metric("Attrition rate", f"{kpis['attrition_rate_pct']}%")
k[2].metric("Avg review score", kpis["avg_review_score"])
k[3].metric("Avg job satisfaction (1-4)", kpis["avg_job_satisfaction"])
k[4].metric("Avg work-life balance (1-4)", kpis["avg_work_life_balance"])

tab_yoy, tab_top, tab_attr, tab_proj, tab_hist = st.tabs([
    "Year-over-year", "Top employees", "Attrition risk", "Project bottlenecks", "Employee history (SCD2)"
])

# TAB 1: YEAR OVER YEAR
with tab_yoy:
    st.subheader("Performance trend by year")
    departments = get_data("get_department_names") or []
    choice = st.selectbox("Department", ["All departments"] + departments, key="yoy_dept")
    
    if choice == "All departments":
        overall = get_data("yoy_overall")
        by_dept = get_data("yoy_performance", None)
        
        if overall is not None and not overall.empty:
            fig = px.line(overall, x="review_year", y="average_review_score", markers=True, title="Company-wide average review score")
            fig.update_xaxes(dtick=1)
            st.plotly_chart(fig)
            
        if by_dept is not None and not by_dept.empty:
            fig = px.line(by_dept, x="review_year", y="average_review_score", color="department_name", markers=True, title="Average review score by department")
            fig.update_xaxes(dtick=1)
            st.plotly_chart(fig)
            
            change = px.bar(by_dept.dropna(subset=["score_change_from_prior_year"]), x="review_year", y="score_change_from_prior_year", color="department_name", barmode="group", title="Change in score vs. the previous year")
            change.update_xaxes(dtick=1)
            st.plotly_chart(change)
            st.dataframe(by_dept, hide_index=True)
    else:
        one = get_data("yoy_performance", choice)
        if one is not None and not one.empty:
            fig = px.line(one, x="review_year", y="average_review_score", markers=True, title=f"{choice}: average review score")
            fig.update_xaxes(dtick=1)
            st.plotly_chart(fig)
            
            change = px.bar(one.dropna(subset=["score_change_from_prior_year"]), x="review_year", y="score_change_from_prior_year", title="Change vs. the previous year")
            change.update_xaxes(dtick=1)
            st.plotly_chart(change)
            st.dataframe(one, hide_index=True)
        else:
            st.info("No review data for this department.")

# TAB 2: TOP EMPLOYEES (DENSE RANK)
with tab_top:
    st.subheader("Top-performing employees by department")
    years = get_data("get_years") or []
    departments = get_data("get_department_names") or []
    
    c1, c2, c3 = st.columns(3)
    year = c1.selectbox("Year", years, key="top_year") if years else None
    dept_choice = c2.selectbox("Department", ["All departments"] + departments, key="top_dept")
    top_n = c3.slider("Show top", min_value=1, max_value=10, value=5)
    
    if year is not None:
        dept_filter = None if dept_choice == "All departments" else dept_choice
        top = get_data("top_employees", int(year), dept_filter, int(top_n))
        if top is None or top.empty:
            st.info("No reviews found for these filters.")
        else:
            fig = px.bar(top, x="average_review_score", y="employee_name", color="department_name", orientation="h", hover_data=["department_rank"], title=f"Top {top_n} employees per department in {year}")
            fig.update_layout(yaxis={"categoryorder": "total ascending"})
            st.plotly_chart(fig)
            st.dataframe(top, hide_index=True)

# TAB 3: ATTRITION
with tab_attr:
    st.subheader("Attrition by department")
    attr = get_data("attrition_by_department")
    if attr is not None and not attr.empty:
        fig = px.bar(attr, x="department_name", y="attrition_rate_pct", text="attrition_rate_pct", title="Attrition rate (%) by department")
        st.plotly_chart(fig)
        st.dataframe(attr, hide_index=True)
        
    st.subheader("Employees at risk of leaving")
    st.caption("Risk score = (4 - job satisfaction) + (4 - work-life balance). Only employees who have NOT left yet are shown.")
    n_risk = st.slider("Number of employees", min_value=10, max_value=200, value=50, step=10)
    risk = get_data("attrition_risk", int(n_risk))
    
    if risk is not None and not risk.empty:
        counts = risk["risk_level"].value_counts()
        m = st.columns(3)
        m[0].metric("High risk", int(counts.get("High", 0)))
        m[1].metric("Medium risk", int(counts.get("Medium", 0)))
        m[2].metric("Low risk", int(counts.get("Low", 0)))
        
        fig = px.scatter(risk, x="average_job_satisfaction", y="average_work_life_balance", color="risk_level", hover_name="employee_name", hover_data=["department_name", "job_role", "risk_score"], color_discrete_map={"High": "red", "Medium": "orange", "Low": "green"}, title="Satisfaction vs. work-life balance")
        st.plotly_chart(fig)
        st.dataframe(risk, hide_index=True)
    else:
        st.info("No risk data available.")

# TAB 4: PROJECT BOTTLENECKS
with tab_proj:
    st.subheader("Project workload and review quality")
    st.caption("Busy = people are allocated more than on most projects. Low scores = reviews are lower than on most projects. Critical = both.")
    bottle = get_data("project_bottlenecks")
    
    if bottle is None or bottle.empty:
        st.info("No project data available.")
    else:
        counts = bottle["flag"].value_counts()
        m = st.columns(4)
        for column, name in zip(m, ["Critical", "Busy", "Low scores", "OK"]):
            column.metric(name, int(counts.get(name, 0)))
            
        plot_df = bottle.dropna(subset=["avg_allocation_pct", "average_review_score"]).copy()
        plot_df["budget"] = plot_df["budget"].fillna(0)
        
        if not plot_df.empty:
            fig = px.scatter(plot_df, x="avg_allocation_pct", y="average_review_score", color="flag", size="budget", size_max=30, hover_name="project_name", hover_data=["department_name", "assigned_employee_count", "status"], color_discrete_map={"Critical": "red", "Busy": "orange", "Low scores": "gold", "OK": "green"}, title="Average allocation per person vs. average review score")
            st.plotly_chart(fig)
            
        wanted = st.multiselect("Show projects flagged as", ["Critical", "Busy", "Low scores", "OK"], default=["Critical", "Busy", "Low scores"])
        st.dataframe(bottle[bottle["flag"].isin(wanted)], hide_index=True)
        
        status_counts = get_data("project_status_counts")
        if status_counts is not None and not status_counts.empty:
            fig = px.bar(status_counts, x="status", y="projects", text="projects", title="Projects by status")
            st.plotly_chart(fig)

# TAB 5: EMPLOYEE HISTORY (SCD TYPE 2)
with tab_hist:
    st.subheader("Full history of one employee")
    st.caption("Each row is one version. The old versions are closed (is_current = 0); the newest row is the current one.")
    emp_id = st.number_input("Employee id", min_value=1, value=1, step=1)
    hist = get_data("employee_history", int(emp_id))
    
    if hist is None or hist.empty:
        st.info("No history found for this employee id.")
    else:
        chart = hist.copy()
        is_current = chart["is_current"].astype(bool)
        
        # The current version ends on 9999-12-31, which can't be drawn - use today instead.
        chart["end_plot"] = [date.today() if cur else end for cur, end in zip(is_current, chart["end_date"])]
        chart["start_plot"] = pd.to_datetime(chart["start_date"])
        chart["end_plot"] = pd.to_datetime(chart["end_plot"])
        chart["version"] = chart["department_name"] + " / " + chart["job_role"]
        chart["employee"] = "Employee " + chart["employee_id"].astype(str)
        
        fig = px.timeline(chart, x_start="start_plot", x_end="end_plot", y="employee", color="version", hover_data=["monthly_income", "job_level"], title="Versions over time")
        st.plotly_chart(fig)
        
        table = hist.copy()
        table["end_date"] = table["end_date"].astype(str).where(~is_current, "current")
        st.dataframe(table, hide_index=True)