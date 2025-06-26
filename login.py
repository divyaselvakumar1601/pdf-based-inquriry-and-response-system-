import streamlit as st
import bcrypt
from index import users_collection

def login_page():
    if "auth_mode" not in st.session_state:
        st.session_state["auth_mode"] = "login"

    apply_clean_dark_style()

    st.markdown("<div class='fullpage'>", unsafe_allow_html=True)

    if st.session_state["auth_mode"] == "signup":
        show_signup()
    else:
        show_login()

    st.markdown("</div>", unsafe_allow_html=True)

def show_login():
    st.markdown("<h3 class='form-title'>🔐 Login</h3>", unsafe_allow_html=True)
    with st.form("login_form"):
        username = st.text_input(" ", key="login_username", placeholder="Username", label_visibility="collapsed")
        password = st.text_input(" ", type="password", key="login_password", placeholder="Password", 
                               label_visibility="collapsed")
        submitted = st.form_submit_button("Login")

        if submitted:
            user = users_collection.find_one({"username": username})
            if user and bcrypt.checkpw(password.encode(), user["password"]):
                st.session_state["authenticated"] = True
                st.session_state["username"] = username
                st.success(f"✅ Welcome back, {user['first_name']}!")
                st.rerun()
            else:
                st.error("Invalid username or password.")

    if st.button("Don't have an account? Sign up"):
        st.session_state["auth_mode"] = "signup"
        st.rerun()

def show_signup():
    st.markdown("<h3 class='form-title'>📝 Sign Up</h3>", unsafe_allow_html=True)
    with st.form("signup_form"):
        first = st.text_input(" ", key="signup_first", placeholder="First Name", label_visibility="collapsed")
        last = st.text_input(" ", key="signup_last", placeholder="Last Name", label_visibility="collapsed")
        username = st.text_input(" ", key="signup_username", placeholder="Username", label_visibility="collapsed")
        password = st.text_input(" ", type="password", key="signup_password", placeholder="Password", 
                               label_visibility="collapsed")
        confirm = st.text_input(" ", type="password", key="signup_confirm", placeholder="Confirm Password", 
                              label_visibility="collapsed")
        submitted = st.form_submit_button("Sign Up")

        if submitted:
            if not all([first, last, username, password, confirm]):
                st.warning("Please fill out all fields.")
            elif password != confirm:
                st.error("Passwords do not match.")
            elif users_collection.find_one({"username": username}):
                st.error("Username already exists.")
            else:
                hashed_pw = bcrypt.hashpw(password.encode(), bcrypt.gensalt())
                users_collection.insert_one({
                    "first_name": first,
                    "last_name": last,
                    "username": username,
                    "password": hashed_pw
                })
                st.success("✅ Registration successful. Please log in.")
                st.session_state["auth_mode"] = "login"
                st.rerun()

    if st.button("Already have an account? Login"):
        st.session_state["auth_mode"] = "login"
        st.rerun()

def apply_clean_dark_style():
    st.markdown("""
    <style>
    /* Background image */
    .fullpage {
        position: fixed;
        top: 0;
        left: 0;
        width: 100vw;
        height: 100vh;
        background: linear-gradient(rgba(0, 0, 0, 0.7), rgba(0, 0, 0, 0.7)), 
                    url('https://i.postimg.cc/nh03xVZ5/loggin.jpg');
        background-size: cover;
        background-position: center;
        display: flex;
        flex-direction: column;
        justify-content: center;
        align-items: center;
        padding: 2rem;
    }

    /* Form title */
    .form-title {
        font-size: 2rem;
        margin-bottom: 1.5rem;
        color: #fff;
        font-weight: 600;
        text-align: center;
    }

    /* Form container */
    .stForm {
        max-width: 350px !important;
        width: 100% !important;
        margin: 0 auto !important;
        padding: 20px;
        border-radius: 10px;
        background-color: rgba(0, 0, 0, 0.7);
        backdrop-filter: blur(5px);
    }

    /* All text inputs */
    .stTextInput > div > div > input {
        width: 100% !important;
        padding: 12px !important;
        border-radius: 8px !important;
        border: 1px solid #444 !important;
        background-color: rgba(255, 255, 255, 0.1) !important;
        color: white !important;
        font-size: 14px !important;
    }

    /* Remove password eye icon */
    [data-testid="stDecoration"] {
        display: none !important;
    }

    /* Buttons */
    .stButton > button {
        width: 100% !important;
        max-width: 200px !important;
        margin: 10px auto !important;
        padding: 12px !important;
        font-size: 15px !important;
        border-radius: 8px !important;
        background-color: #0f52ba !important;
        color: white !important;
        border: none !important;
        display: block !important;
        transition: all 0.3s ease !important;
    }

    /* Center align form submit button */
    .stForm .stButton {
        display: flex !important;
        justify-content: center !important;
        width: 100% !important;
    }

    /* Button hover effect */
    .stButton > button:hover {
        background-color: #1a6fd9 !important;
        transform: translateY(-1px) !important;
    }

    /* Alert messages */
    .stAlert {
        max-width: 350px !important;
        margin: 0 auto 15px auto !important;
        border-radius: 8px !important;
    }

    /* Toggle buttons (Sign up/Login) */
    .stButton:not(.stForm .stButton) > button {
        background-color: transparent !important;
        border: 1px solid #0f52ba !important;
        margin-top: 20px !important;
    }

    @media screen and (max-width: 480px) {
        .stForm {
            width: 90% !important;
            padding: 15px !important;
        }
        
        .form-title {
            font-size: 1.5rem !important;
        }
    }
    </style>
    """, unsafe_allow_html=True)