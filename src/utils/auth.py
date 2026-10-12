"""Authentication and role-based access helpers for the Streamlit app."""

from __future__ import annotations

from typing import Final, Literal

import streamlit as st
from sqlalchemy.exc import SQLAlchemyError

from src.auth_manager import AuthManager

Role = Literal["Admin", "Viewer"]

SESSION_AUTHENTICATED: Final = "authenticated"
SESSION_USERNAME: Final = "username"
SESSION_ROLE: Final = "role"


def authenticate(username: str, password: str) -> Role | None:
    """Return the database-configured user's role when credentials are valid."""
    role = AuthManager().authenticate(username, password)
    return role if role in ("Admin", "Viewer") else None


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
    st.write("Enter your StaffSync credentials to continue.")

    with st.form("login_form"):
        username = st.text_input("Username", autocomplete="username")
        password = st.text_input("Password", type="password", autocomplete="current-password")
        submitted = st.form_submit_button("Log in", type="primary")

    if submitted:
        try:
            role = authenticate(username, password)
        except SQLAlchemyError:
            st.error("Unable to access the authentication database.")
            return

        if role is None:
            st.error("Invalid username or password.")
        else:
            log_in(username, role)
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
