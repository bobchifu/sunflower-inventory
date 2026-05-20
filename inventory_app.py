import streamlit as st
import pandas as pd
import sqlite3
import fitz  # PyMuPDF
import re
from datetime import datetime
from fpdf import FPDF
import os

# --- CONFIG & STYLING ---
st.set_page_config(page_title="Sunflower Inventory Pro", layout="wide")

# Initialize Session States
if 'current_step' not in st.session_state:
    st.session_state.current_step = 0
if 'confirm_wipe' not in st.session_state:
    st.session_state.confirm_wipe = False

# Custom CSS
st.markdown("""
    <style>
    @import url('https://fonts.googleapis.com/css2?family=Inter:wght@400;700;800&display=swap');
    html, body, [class*="css"] { font-family: 'Inter', sans-serif; }
    .main-header { text-align: center; padding: 10px; margin-bottom: 20px; }
    .header-text {
        font-family: 'Inter', sans-serif; font-weight: 800; font-size: 42px;
        letter-spacing: 2px; color: #1E1E1E; margin-top: -10px; text-transform: uppercase;
    }
    </style>
    """, unsafe_allow_html=True)

# --- DATABASE ENGINE ---
DB_NAME = 'sunflower_pro_v17.db'

def init_db():
    conn = sqlite3.connect(DB_NAME, check_same_thread=False)
    c = conn.cursor()
    c.execute('''CREATE TABLE IF NOT EXISTS inventory 
                 (id INTEGER PRIMARY KEY, name TEXT UNIQUE, category TEXT, 
                  manual_stock INTEGER DEFAULT 0, last_sales_qty INTEGER DEFAULT 0,
                  reorder_level INTEGER DEFAULT 5, last_updated TEXT)''')
    conn.commit()
    return conn

conn = init_db()

def reset_database():
    c = conn.cursor()
    c.execute("DELETE FROM inventory")
    conn.commit()
    st.session_state.current_step = 0
    st.session_state.confirm_wipe = False
    st.rerun()

# --- HEADER (LOGO & NAME) ---
col_l, col_m, col_r = st.columns([1, 1, 1])
with col_m:
    if os.path.exists("logo.png"):
        st.image("logo.png", use_container_width=True)

st.markdown('<div class="main-header"><h1 class="header-text">SUNFLOWER LOUNGE & RESTAURANT</h1></div>', unsafe_allow_html=True)

# --- NAVIGATION ---
nav_col1, nav_col2, nav_col3 = st.columns([1,1,1])
with nav_col1:
    if st.button("📋 1. INVENTORY BALANCE", use_container_width=True, 
                 type="primary" if st.session_state.current_step == 0 else "secondary"):
        st.session_state.current_step = 0
        st.rerun()
with nav_col2:
    if st.button("📤 2. UPLOAD & SYNC", use_container_width=True, 
                 type="primary" if st.session_state.current_step == 1 else "secondary"):
        st.session_state.current_step = 1
        st.rerun()
with nav_col3:
    if st.button("📜 3. FINAL REPORT", use_container_width=True, 
                 type="primary" if st.session_state.current_step == 2 else "secondary"):
        st.session_state.current_step = 2
        st.rerun()

# --- PARSING ENGINE ---
def process_report(file):
    raw_text = ""
    f_ext = file.name.lower().split('.')[-1]
    if f_ext in ['pdf', 'xps']:
        doc = fitz.open(stream=file.read(), filetype=f_ext)
        for page in doc:
            raw_text += page.get_text() + "\n"
    else:
        raw_text = file.getvalue().decode("utf-8").replace('"', '')
    
    date_match = re.findall(r"(\d{1,2}\s+[A-Za-z]+\s+\d{4}\s+\d{2}:\d{2})", raw_text)
    r_date = date_match[-1] if date_match els