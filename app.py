import streamlit as st

from services.authentication import (
    login_user,
    signup_user,
    logout_user
)

st.set_page_config(
    page_title="AegisAI",
    page_icon="🛡️",
    layout="wide"
)


# ==========================================
# LOGIN / SIGNUP
# ==========================================

def show_login():

    st.title("🛡️ AegisAI")

    st.subheader(
        "Intelligent Approval & Compliance System"
    )

    st.write(
        "AI-powered policy intelligence, multi-agent review, "
        "and human-controlled approvals."
    )

    st.divider()

    tab_login, tab_signup = st.tabs([
        "Login",
        "Create Account"
    ])

    # ======================================
    # LOGIN
    # ======================================

    with tab_login:

        st.subheader("Sign In")

        with st.form("login_form"):

            email = st.text_input("Email")

            password = st.text_input(
                "Password",
                type="password"
            )

            submitted = st.form_submit_button(
                "Login",
                type="primary",
                use_container_width=True
            )

        if submitted:

            email = email.strip()

            if not email:

                st.error(
                    "Please enter your email."
                )

            elif not password:

                st.error(
                    "Please enter your password."
                )

            else:

                success, message = login_user(
                    email,
                    password
                )

                if success:

                    st.success(message)

                    st.rerun()

                else:

                    st.error(message)

    # ======================================
    # CREATE ACCOUNT
    # ======================================

    with tab_signup:

        st.subheader("Create Account")

        with st.form("signup_form"):

            name = st.text_input("Full Name")

            email = st.text_input("Email")

            password = st.text_input(
                "Password",
                type="password"
            )

            confirm_password = st.text_input(
                "Confirm Password",
                type="password"
            )

            submitted = st.form_submit_button(
                "Create Account",
                type="primary",
                use_container_width=True
            )

        if submitted:

            name = name.strip()
            email = email.strip()

            if not name:

                st.error(
                    "Please enter your full name."
                )

            elif not email:

                st.error(
                    "Please enter your email."
                )

            elif not password:

                st.error(
                    "Please enter a password."
                )

            elif not confirm_password:

                st.error(
                    "Please confirm your password."
                )

            elif password != confirm_password:

                st.error(
                    "Passwords do not match."
                )

            elif len(password) < 6:

                st.error(
                    "Password must contain at least 6 characters."
                )

            else:

                success, message = signup_user(
                    name,
                    email,
                    password
                )

                if success:

                    st.success(
                        "Account created successfully."
                    )

                    st.rerun()

                else:

                    st.error(message)


# ==========================================
# MAIN APPLICATION
# ==========================================

def show_application():

    user = st.session_state["user"]

    # --------------------------------------
    # SIDEBAR
    # --------------------------------------

    with st.sidebar:

        st.title("🛡️ AegisAI")

        st.write(
            "Approval & Compliance System"
        )

        st.divider()

        st.write(
            f"**User:** {user.email}"
        )

        st.divider()

        st.subheader("Navigation")

        if st.button(
            "📊 Dashboard",
            use_container_width=True
        ):

            st.switch_page(
                "pages/1_Dashboard.py"
            )

        if st.button(
            "📝 Create Approval Case",
            use_container_width=True
        ):

            st.switch_page(
                "pages/2_Create_Case.py"
            )

        if st.button(
            "⚖️ Decision",
            use_container_width=True
        ):

            st.switch_page(
                "pages/4_Decision.py"
            )

        if st.button(
            "📁 Case History",
            use_container_width=True
        ):

            st.switch_page(
                "pages/5_Case_History.py"
            )

        if st.button(
            "📄 Reports",
            use_container_width=True
        ):

            st.switch_page(
                "pages/6_Report.py"
            )

        st.divider()

        if st.button(
            "Logout",
            use_container_width=True
        ):

            logout_user()

            st.rerun()

    # --------------------------------------
    # MAIN SCREEN
    # --------------------------------------

    st.title("🛡️ AegisAI")

    st.subheader(
        "Intelligent Approval & Compliance System"
    )

    st.write(
        "AI-powered policy intelligence, multi-agent review, "
        "and human-controlled approvals."
    )

    st.divider()

    st.success(
        f"Welcome, {user.email}"
    )

    st.subheader(
        "Approval Management"
    )

    col1, col2 = st.columns(2)

    # ======================================
    # DASHBOARD CARD
    # ======================================

    with col1:

        st.markdown(
            "### 📊 Dashboard"
        )

        st.write(
            "View approval cases, their status, "
            "and recent activity."
        )

        if st.button(
            "Open Dashboard",
            use_container_width=True
        ):

            st.switch_page(
                "pages/1_Dashboard.py"
            )

    # ======================================
    # CREATE CASE CARD
    # ======================================

    with col2:

        st.markdown(
            "### 📝 Create Approval Case"
        )

        st.write(
            "Create a procurement or capital "
            "expenditure approval case."
        )

        if st.button(
            "➕ Create New Case",
            type="primary",
            use_container_width=True
        ):

            st.switch_page(
                "pages/2_Create_Case.py"
            )

    st.divider()

    # ======================================
    # SYSTEM STATUS
    # ======================================

    st.subheader("System Status")

    col1, col2, col3 = st.columns(3)

    with col1:

        st.success(
            "🔐 Authentication\n\nConnected"
        )

    with col2:

        st.success(
            "🗄️ Supabase Database\n\nConnected"
        )

    with col3:

        st.info(
            "🤖 AI Review\n\nReady"
        )


# ==========================================
# ENTRY POINT
# ==========================================

if (
    "user" not in st.session_state
    or st.session_state["user"] is None
):

    show_login()

else:

    show_application()
