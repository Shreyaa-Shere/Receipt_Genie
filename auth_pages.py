import streamlit as st
from models import User, Session
from session_utils import create_session
import re

def is_valid_email(email):
    pattern = r'^[\w\.-]+@[\w\.-]+\.\w+$'
    return re.match(pattern, email) is not None

def show_login_page():
    st.markdown(
        """
        <style>
        .login-container, .register-container {
            max-width: 240px !important;
            margin: 0 auto !important;
            padding: 2rem;
            background: var(--card-bg);
            border-radius: 10px;
            box-shadow: 0 2px 8px rgba(0,0,0,0.1);
        }
        .login-title, .register-title {
            text-align: center;
            color: var(--primary-color);
            margin-bottom: 2rem;
        }
        .login-container .stTextInput input,
        .register-container .stTextInput input,
        .login-container input[type="text"],
        .login-container input[type="password"],
        .register-container input[type="text"],
        .register-container input[type="password"] {
            width: 100% !important;
            max-width: 220px !important;
            min-width: 0 !important;
            margin: 0 auto 1.2em auto !important;
            display: block !important;
            box-sizing: border-box !important;
        }
        </style>
        """,
        unsafe_allow_html=True
    )
    with st.container():
        st.markdown('<div class="login-container">', unsafe_allow_html=True)
        st.markdown('<h1 class="login-title">Login to Receipt Genie</h1>', unsafe_allow_html=True)

        email = st.text_input("Email", value="", key="login_email")
        password = st.text_input("Password", type="password", value="", key="login_password")
        
        col1, col2 = st.columns([1, 1])
        
        with col1:
            if st.button("Login", use_container_width=True):
                if not email or not password:
                    st.error("Please fill in all fields")
                    return False
                
                if not is_valid_email(email):
                    st.error("Please enter a valid email address")
                    return False
                
                session = Session()
                user = session.query(User).filter_by(email=email).first()
                
                if user and user.check_password(password):
                    token = create_session(email)
                    st.session_state['authenticated'] = True
                    st.session_state['user_email'] = email
                    st.session_state['session_token'] = token
                    st.query_params['session'] = token
                    st.success("Login successful!")
                    st.rerun()
                else:
                    st.error("Invalid email or password")
                session.close()
        
        with col2:
            if st.button("Create Account", use_container_width=True):
                st.session_state['show_register'] = True
                st.rerun()
        
        st.markdown('</div>', unsafe_allow_html=True)
        return False

def show_register_page():
    st.markdown(
        """
        <style>
        .register-container {
            max-width: 200px;
            margin: 0 auto;
            padding: 2rem;
            background: var(--card-bg);
            border-radius: 10px;
            box-shadow: 0 2px 8px rgba(0,0,0,0.1);
        }
        .register-title {
            text-align: center;
            color: var(--primary-color);
            margin-bottom: 2rem;
        }
        .login-container input[type="text"],
        .login-container input[type="password"],
        .register-container input[type="text"],
        .register-container input[type="password"] {
            width: 100% !important;
            max-width: 220px !important;
            min-width: 0 !important;
            margin: 0 auto 1.2em auto !important;
            display: block !important;
        }
        </style>
        """,
        unsafe_allow_html=True
    )
    with st.container():
        st.markdown('<div class="register-container">', unsafe_allow_html=True)
        st.markdown('<h1 class="register-title">Create Account</h1>', unsafe_allow_html=True)

        email = st.text_input("Email", value="", key="register_email")
        password = st.text_input("Password", type="password", value="", key="register_password")
        confirm_password = st.text_input("Confirm Password", type="password", value="", key="register_confirm_password")
        
        col1, col2 = st.columns([1, 1])
        
        with col1:
            if st.button("Register", use_container_width=True):
                if not email or not password or not confirm_password:
                    st.error("Please fill in all fields")
                    return
                
                if not is_valid_email(email):
                    st.error("Please enter a valid email address")
                    return
                
                if password != confirm_password:
                    st.error("Passwords do not match")
                    return
                
                if len(password) < 6:
                    st.error("Password must be at least 6 characters long")
                    return
                
                session = Session()
                existing_user = session.query(User).filter_by(email=email).first()
                
                if existing_user:
                    st.error("Email already registered")
                    session.close()
                    return
                
                new_user = User(email=email)
                new_user.set_password(password)
                
                session.add(new_user)
                session.commit()
                session.close()
                
                st.success("Account created successfully! Please login.")
                st.session_state['show_register'] = False
                st.rerun()
        
        with col2:
            if st.button("Back to Login", use_container_width=True):
                st.session_state['show_register'] = False
                st.rerun()
        
        st.markdown('</div>', unsafe_allow_html=True) 