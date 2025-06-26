import streamlit as st

# THIS MUST BE FIRST
st.set_page_config(page_title="PDF Inquiry and Response", page_icon="📄", layout="wide")

# Now import the other modules
from login import login_page
from chat import chat_page

# App logic
if "authenticated" not in st.session_state:
    st.session_state["authenticated"] = False

if not st.session_state["authenticated"]:
    login_page()
else:
    chat_page()
