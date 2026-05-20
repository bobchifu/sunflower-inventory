import streamlit as st
import pandas as pd
import sqlite3
import fitz  # PyMuPDF for PDF and XPS
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

# Custom CSS for UI
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
DB_NAME = 'sunflower_pro_v16.db'

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
    # Reset all states and refresh
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
    if st.button("📋 1. INVENTORY BALANCE", use_container_width=True, type="primary" if st.session_state.current_step == 0 else "secondary"):
        st.session_state.current_step = 0
        st.rerun()
with nav_col2:
    if st.button("📤 2. UPLOAD & SYNC", use_container_width=True, type="primary" if st.session_state.current_step == 1 else "secondary"):
        st.session_state.current_step = 1
        st.rerun()
with nav_col3:
    if st.button("📜 3. FINAL REPORT", use_container_width=True, type="primary" if st.session_state.current_step == 2 else "secondary"):
        st.session_state.current_step = 2
        st.rerun()

# --- PARSING ENGINE ---
def process_report(file):
    raw_text = ""
    file_ext = file.name.lower().split('.')[-1]
    if file_ext in ['pdf', 'xps']:
        doc = fitz.open(stream=file.read(), filetype=file_ext)
        for page in doc:
            raw_text += page.get_text() + "\n"
    else:
        raw_text = file.getvalue().decode("utf-8").replace('"', '')
    
    date_match = re.findall(r"(\d{1,2}\s+[A-Za-z]+\s+\d{4}\s+\d{2}:\d{2})", raw_text)
    report_date = date_match[-1] if date_match else datetime.now().strftime("%d %b %Y %H:%M")
    
    # Pattern to find Product | Qty | Price
    product_pattern = re.compile(r"^(.+?)\s+(\d+)\s+([\d,]+\.\d{2})$", re.MULTILINE)
    matches = product_pattern.findall(raw_text)
    extracted = []
    for m in matches:
        name = m[0].strip().upper()
        if "TOTAL" in name or "SNOOKER" in name: continue
        extracted.append({"name": name, "qty": int(m[1])})
    return extracted, report_date

# --- DATA PROCESSING ---
df_db = pd.read_sql_query("SELECT * FROM inventory", conn)

# --- STEP 1: BALANCE ---
if st.session_state.current_step == 0:
    st.header("Step 1: Record Opening Balance")
    
    if df_db.empty:
        st.info("The system is empty. Initialize common products or upload a report.")
        c1, c2 = st.columns(2)
        if c1.button("✨ Initialize Common Products (Qty 0)", use_container_width=True):
            defaults = [
                ("WATER", "SOFTS / BEERS"), ("HEINEKEN", "SOFTS / BEERS"), 
                ("DESPERADO", "SOFTS / BEERS"), ("D/BLACK", "SOFTS / BEERS"), 
                ("MALTA", "SOFTS / BEERS"), ("FAYROUZ", "SOFTS / BEERS"),
                ("TIGER", "SOFTS / BEERS"), ("LIFE", "SOFTS / BEERS"),
                ("ORIGIN BITTERS", "SOFTS / BEERS"), ("SHISHA BIG", "SHISHA")
            ]
            for name, cat in defaults:
                conn.execute("INSERT OR IGNORE INTO inventory (name, category, manual_stock) VALUES (?,?,0)", (name, cat))
            conn.commit()
            st.rerun()
        
        up_stock = c2.file_uploader("Upload Stock Report", type=["pdf", "xps", "csv"])
        if up_stock:
            items, r_date = process_report(up_stock)
            if items and st.button("🚀 Set as Initial Balance"):
                for item in items:
                    conn.execute("INSERT INTO inventory (name, manu