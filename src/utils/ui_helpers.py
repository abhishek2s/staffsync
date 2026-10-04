import streamlit as st
from src.dal.analytics_manager import AnalyticsManager
from src.dal.employee_manager import EmployeeManager

def setup_page(title):
    st.set_page_config(page_title=f"StaffSync | {title}", layout="wide")
    
    with st.sidebar:
        # Cyan typographic logo to match the dark theme
        st.markdown(
            """
            <div style='padding-bottom: 20px;'>
                <h2 style='margin: 0; padding: 0; color: #10b981; font-weight: 800; font-size: 2.2rem; letter-spacing: -1px;'>StaffSync</h2>
                <p style='margin: 0; padding-top: 2px; color: #94a3b8; font-size: 0.95rem; font-weight: 500;'>People intelligence platform</p>
            </div>
            """, 
            unsafe_allow_html=True
        )
        
        # Cyan section headers
        st.markdown("<p style='font-size: 11px; font-weight: 700; color: #10b981; letter-spacing: 1px; margin-bottom: 8px; text-transform: uppercase;'>WORKSPACE</p>", unsafe_allow_html=True)
        st.caption("Use the pages above to explore workforce insights or manage employee, project, and review data.")
        
        st.divider()
        
        st.markdown("<p style='font-size: 11px; font-weight: 700; color: #10b981; letter-spacing: 1px; margin-bottom: 8px; text-transform: uppercase;'>DATA WAREHOUSE</p>", unsafe_allow_html=True)
        st.caption("Employee changes sync to the warehouse immediately. New projects and reviews appear after a refresh.")
        
        st.write("") 
        
        # The 'primary' type automatically pulls the coral-red from Streamlit's default dark theme
        if st.button("Refresh Data", type="primary", use_container_width=True):
            with st.spinner("Rebuilding the warehouse..."):
                ok, message = AnalyticsManager().refresh_warehouse()
                show_result(ok, message)

def show_result(ok, message):
    if ok:
        st.toast(message, icon="✅")
        st.cache_data.clear()
    else:
        st.error(message, icon="🚨")

@st.cache_data(ttl=300, show_spinner="Loading data...")
def _cached_analytics(method_name, *args):
    return getattr(AnalyticsManager(), method_name)(*args)

def get_data(method_name, *args):
    try:
        return _cached_analytics(method_name, *args)
    except Exception as err:
        st.error(f"Could not load data from the warehouse: {err}")
        return None

@st.cache_data(ttl=300)
def load_departments():
    return EmployeeManager().get_departments()