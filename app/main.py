import sys
from pathlib import Path

# Make src and config importable when Streamlit runs this file
PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

import streamlit as st
from src.utils.ui_helpers import get_data, setup_page

# Setup page
setup_page("Home", "🏠")

# --- CSS for Premium Dark Mode Cards ---
st.markdown("""
<style>
/* Style the metrics to look like elevated background cards */
[data-testid="stMetric"] {
    background-color: #1e2127; /* Dark slate background */
    border: 1px solid #333842; /* Subtle border */
    border-radius: 8px;
    padding: 15px 20px;
    box-shadow: 0 4px 6px rgba(0, 0, 0, 0.3);
}
/* Soften the metric labels */
[data-testid="stMetricLabel"] {
    color: #94a3b8;
    font-size: 14px;
    margin-bottom: 5px;
}
</style>
""", unsafe_allow_html=True)

# Premium Header Section
st.title("StaffSync Employee Analytics")
st.write("Track employee performance, attrition and project workload using a Bronze Silver Gold data warehouse.")
st.write("") 

# Fetch Data
kpis = get_data("get_kpis")
if kpis is None:
    st.stop() 

# --- KEY NUMBERS SECTION ---
st.subheader("Key numbers")

row1 = st.columns(4)
row1[0].metric("Employees (current)", f"{kpis['total_employees']:,}")
row1[1].metric("Attrition rate", f"{kpis['attrition_rate_pct']:.2f}%")
row1[2].metric("Average review score", f"{kpis['avg_review_score']:.2f}")
row1[3].metric("Total reviews", f"{kpis['total_reviews']:,}")

st.write("") 

row2 = st.columns(4)
row2[0].metric("Projects", f"{kpis['total_projects']:,}")
row2[1].metric("Total project budget", f"${kpis['total_project_budget']:,.0f}")
row2[2].metric("Average performance rating (1-4)", f"{kpis['avg_performance_rating']:.2f}")
row2[3].metric("Over-allocated employees", f"{kpis['overallocated_employees']:,}", help="Employees whose project allocations add up to more than 100%.")

st.write("")
st.divider()
st.write("")

# --- NAVIGATION OVERVIEW SECTION ---
left, right = st.columns(2, gap="large")

with left:
    # Use native bordered containers for the lower sections to match the cards
    with st.container(border=True):
        st.markdown("### Data Entry")
        st.write("Onboard employees, change their department or salary (creates SCD Type 2 history), create projects, assign people and submit reviews.")
        # st.caption("Use the pages in the left sidebar.")

with right:
    with st.container(border=True):
        st.markdown("### Analytics")
        st.write("Year-over-year trends, top performers, attrition risk, project bottlenecks and the full history of any employee.")
        st.write("") # Spacer to balance the height with the left card