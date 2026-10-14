"""Authentication and role-based access helpers for the Streamlit app."""

from __future__ import annotations

from typing import Final, Literal

import streamlit as st
from sqlalchemy.exc import IntegrityError, SQLAlchemyError

from src.dal.auth_manager import AuthManager

Role = Literal["Admin", "Viewer"]

SESSION_AUTHENTICATED: Final = "authenticated"
SESSION_USERNAME: Final = "username"
SESSION_ROLE: Final = "role"


def authenticate(username: str, password: str) -> Role | None:
    """Return the database-configured user's role when credentials are valid."""
    role = AuthManager().authenticate(username, password)
    return role if role in ("Admin", "Viewer") else None


def register_employee(email: str, password: str) -> Role:
    """Create an account for a known employee and return its department-based role."""
    role = AuthManager().register_employee(email, password)
    if role not in ("Admin", "Viewer"):
        raise ValueError("The employee's department does not have a valid StaffSync role.")
    return role


def is_authenticated() -> bool:
    return bool(st.session_state.get(SESSION_AUTHENTICATED, False))


def current_role() -> Role | None:
    role = st.session_state.get(SESSION_ROLE)
    return role if role in ("Admin", "Viewer") else None


def current_username() -> str | None:
    username = st.session_state.get(SESSION_USERNAME)
    return username if isinstance(username, str) else None


def log_in(username: str, role: Role) -> None:
    st.session_state[SESSION_AUTHENTICATED] = True
    st.session_state[SESSION_USERNAME] = username.strip()
    st.session_state[SESSION_ROLE] = role


def log_out() -> None:
    for key in (SESSION_AUTHENTICATED, SESSION_USERNAME, SESSION_ROLE):
        st.session_state.pop(key, None)


def render_login() -> None:
    """Render the login screen and stop page execution."""
    st.title("Sign in to StaffSync")
    sign_in_tab, sign_up_tab = st.tabs(["Sign in", "Create account"])

    with sign_in_tab:
        st.write("Enter your StaffSync credentials to continue.")
        with st.form("login_form"):
            username = st.text_input("Work email", autocomplete="username")
            password = st.text_input("Password", type="password", autocomplete="current-password")
            submitted = st.form_submit_button("Log in", type="primary")

        if submitted:
            try:
                role = authenticate(username, password)
            except SQLAlchemyError:
                st.error("Unable to access the authentication database.")
                return

            if role is None:
                st.error("Invalid work email or password.")
            else:
                log_in(username, role)
                st.rerun()

    with sign_up_tab:
        st.write("Create an account using the work email on your StaffSync employee record.")
        # st.caption(
        #     "Your role is assigned from your department: Human Resources receives Admin "
        #     "access; Sales and Research & Development receive Viewer access."
        # )
        with st.form("signup_form"):
            email = st.text_input("Work email", autocomplete="email")
            new_password = st.text_input("Password", type="password", autocomplete="new-password")
            confirm_password = st.text_input(
                "Confirm password", type="password", autocomplete="new-password"
            )
            signup_submitted = st.form_submit_button("Create account", type="primary")

        if signup_submitted:
            if new_password != confirm_password:
                st.error("Passwords do not match.")
                return

            try:
                role = register_employee(email, new_password)
            except ValueError as err:
                st.error(str(err))
                return
            except IntegrityError:
                st.error("An account already exists for this work email.")
                return
            except SQLAlchemyError:
                st.error("Unable to access the authentication database.")
                return

            log_in(email.strip().casefold(), role)
            st.success(f"Account created. You are signed in with {role} access.")
            st.rerun()


def require_role(allowed_roles: set[Role]) -> Role:
    """Stop execution unless the current session has an allowed role."""
    role = current_role()
    if not is_authenticated() or role is None:
        render_login()
        st.stop()

    if role not in allowed_roles:
        st.error("Access Denied")
        st.info("Your current role does not have permission to view this page.")
        st.stop()

    return role
