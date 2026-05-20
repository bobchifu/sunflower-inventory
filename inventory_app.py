import streamlit as st
import pandas as pd
import sqlite3
import fitz  # PyMuPDF
import re
from datetime import datetime
from fpdf import FPDF
import os

# --- APP CONFIG ---
st.set_page_config(page_title="Sunflower Inventory", layout="wide")

# Initialize Session States
if 'step' not in st.session_state:
    st.session_state.step = 0
if 'confirm_reset' not in st.session_state:
    st.session_state.confirm_reset = False

# --- CSS FOR BOLD CENTRALISED UI ---
st.markdown("""
    <style>
    @import url('https://fonts.googleapis.com/css2?family=Inter:wght@400;700;800&display=swap');
    html, body, [class*="css"] { font-family: 'Inter', sans-serif; }
    .main-header { text-align: center; padding: 10px; margin-bottom: 20px; }
    .header-text {
        font-family: 'Inter', sans-serif; 
        font-weight: 800; 
        font-size: 42px;
        color: #1E1E1E; 
        text-transform: uppercase;
        letter-spacing: 2px;
    }
    .stMetric { background-color: #ffffff; border: 1px solid #eee; padding: 15px; border-radius: 10px; }
    </style>
    """, unsafe_allow_html=True)

# --- DATABASE LOGIC ---
DB_FILE = 'sunflower_final_system.db'

def get_db_conn():
    conn = sqlite3.connect(DB_FILE, check_same_thread=False)
    conn.execute('''CREATE TABLE IF NOT EXISTS inventory 
                 (id INTEGER PRIMARY KEY, name TEXT UNIQUE, category TEXT, 
                  stock INTEGER DEFAULT 0, sold INTEGER DEFAULT 0,
                  reorder INTEGER DEFAULT 5, date TEXT)''')
    return conn

conn = get_db_conn()

def wipe_system():
    conn.execute("DELETE FROM inventory")
    conn.commit()
    st.session_state.step = 0
    st.session_state.confirm_reset = False
    st.rerun()

# --- REPORT PARSING (PDF, XPS, CSV) ---
def parse_report(file):
    text = ""
    ext = file.name.lower().split('.')[-1]
    if ext in ['pdf', 'xps']:
        doc = fitz.open(stream=file.read(), filetype=ext)
        for page in doc:
            text += page.get_text() + "\n"
    else:
        text = file.getvalue().decode("utf-8").replace('"', '')
    
    # Date Extraction
    d_match = re.findall(r"(\d{1,2}\s+[A-Za-z]+\s+\d{4}\s+\d{2}:\d{2})", text)
    r_date = d_match[-1] if d_match else datetime.now().strftime("%d %b %Y %H:%M")
    
    # Item Extraction
    pattern = re.compile(r"^(.+?)\s+(\d+)\s+([\d,]+\.\d{2})$", re.MULTILINE)
    items = []
    for m in pattern.findall(text):
        name = m[0].strip().upper()
        if "TOTAL" not in name and "SNOOKER" not in name:
            items.append({"name": name, "qty": int(m[1])})
    return items, r_date

# --- HEADER (LOGO & TITLE) ---
c1, c2, c3 = st.columns([1, 1, 1])
with c2:
    if os.path.exists("logo.png"):
        st.image("logo.png", use_container_width=True)

st.markdown(f'<div class="main-header"><h1 class="header-text">SUNFLOWER LOUNGE & RESTAURANT</h1></div>', unsafe_allow_html=True)

# --- NAVIGATION BUTTONS ---
n1, n2, n3 = st.columns(3)
if n1.button("📋 1. INVENTORY BALANCE", use_container_width=True, type="primary" if st.session_state.step == 0 else "secondary"):
    st.session_state.step = 0
    st.rerun()
if n2.button("📤 2. UPLOAD & SYNC", use_container_width=True, type="primary" if st.session_state.step == 1 else "secondary"):
    st.session_state.step = 1
    st.rerun()
if n3.button("📜 3. FINAL REPORT", use_container_width=True, type="primary" if st.session_state.step == 2 else "secondary"):
    st.session_state.step = 2
    st.rerun()

# Load Data from DB
df = pd.read_sql_query("SELECT * FROM inventory", conn)

# --- STEP 1: OPENING BALANCE ---
if st.session_state.step == 0:
    st.header("Step 1: Current Physical Stock")
    
    if df.empty:
        st.info("System is empty. Initialize or upload a report to begin.")
        ca, cb = st.columns(2)
        if ca.button("✨ Initialize Common Drinks (Qty 0)", use_container_width=True):
            defaults = ["WATER", "HEINEKEN", "DESPERADO", "D/BLACK", "MALTA", "FAYROUZ", "TIGER", "LIFE"]
            for d in defaults:
                conn.execute("INSERT OR IGNORE INTO inventory (name, category, stock) VALUES (?,?,?)", (d, "BEERS/SOFTS", 0))
            conn.commit()
            st.rerun()
        
        f = cb.file_uploader("Upload Initial Stock Report", type=['pdf','xps','csv'])
        if f:
            items, r_date = parse_report(f)
            if items and st.button("🚀 Set as Opening Stock"):
                for i in items:
                    conn.execute("INSERT INTO inventory (name, stock, date) VALUES (?,?,?) ON CONFLICT(name) DO UPDATE SET stock=excluded.stock", (i['name'], i['qty'], r_date))
                conn.commit()
                st.rerun()
    
    # Editable Grid
    st.subheader("Manual Stock Adjustment")
    ed = st.data_editor(df[["category", "name", "stock", "reorder"]], use_container_width=True, hide_index=True, num_rows="dynamic")
    
    if st.button("💾 SAVE ALL CHANGES", use_container_width=True):
        conn.execute("DELETE FROM inventory")
        for _, r in ed.iterrows():
            if pd.notna(r['name']) and str(r['name']).strip() != "":
                conn.execute("INSERT OR IGNORE INTO inventory (category, name, stock, reorder) VALUES (?,?,?,?)", (r['category'], r['name'].upper(), r['stock'], r['reorder']))
        conn.commit()
        st.success("Changes Saved.")
        st.rerun()

    if not df.empty:
        if st.button("➡️ NEXT: UPLOAD SALES", use_container_width=True):
            st.session_state.step = 1
            st.rerun()

# --- STEP 2: UPLOAD SALES ---
elif st.session_state.step == 1:
    st.header("Step 2: Upload Sales Report")
    f = st.file_uploader("Upload Sales (.pdf, .xps, .csv)", type=['pdf','xps','csv'])
    if f:
        items, r_date = parse_report(f)
        if items:
            st.write(f"📂 Report Date: {r_date}")
            st.dataframe(pd.DataFrame(items), use_container_width=True)
            if st.button("➖ DEDUCT SALES FROM STOCK", use_container_width=True):
                for i in items:
                    conn.execute("UPDATE inventory SET stock=stock-?, sold=?, date=? WHERE name=?", (i['qty'], i['qty'], r_date, i['name']))
                conn.commit()
                st.success("Sales Deducted!")
            
            if st.button("➡️ NEXT: FINAL REPORT", use_container_width=True):
                st.session_state.step = 2
                st.rerun()

# --- STEP 3: FINAL REPORT ---
elif st.session_state.step == 2:
    st.header("Step 3: Inventory Movement")
    if not df.empty:
        res = df.copy()
        res['Opening'] = res['stock'] + res['sold']
        st.dataframe(res[["category", "name", "Opening", "sold", "stock", "date"]], use_container_width=True, hide_index=True)
        
        st.markdown("---")
        if st.button("📝 GENERATE OFFICIAL PDF", use_container_width=True):
            pdf = FPDF()
            pdf.add_page()
            if os.path.exists("logo.png"):
                pdf.image("logo.png", x=85, y=10, w=40)
                pdf.ln(45)
            pdf.set_font("Arial", 'B', 16)
            pdf.cell(190, 10, "SUNFLOWER LOUNGE & RESTAURANT", ln=True, align='C')
            pdf.ln(10)
            pdf.set_font("Arial", 'B', 10)
            pdf.cell(80, 10, " PRODUCT", 1)
            pdf.cell(30, 10, " START", 1)
            pdf.cell(30, 10, " SOLD", 1)
            pdf.cell(50, 10, " BALANCE", 1, ln=True)
            pdf.set_font("Arial", '', 10)
            for _, r in res.iterrows():
                pdf.cell(80, 10, str(r['name']), 1)
                pdf.cell(30, 10, str(r['Opening']), 1)
                pdf.cell(30, 10, str(r['sold']), 1)
                pdf.cell(50, 10, str(r['stock']), 1, ln=True)
            
            st.download_button("📥 DOWNLOAD PDF", data=pdf.output(dest='S').encode('latin-1'), file_name="report.pdf", use_container_width=True)
    else:
        st.info("No data available.")

# --- RESET FOOTER ---
st.markdown("---")
if not st.session_state.confirm_reset:
    if st.button("🏠 HOME / RESET SYSTEM", use_container_width=True):
        st.session_state.confirm_reset = True
        st.rerun()
else:
    st.error("⚠️ CONFIRM: Wipe all data?")
    cy, cn = st.columns(2)
    if cy.button("✅ YES, WIPE EVERYTHING", use_container_width=True): wipe_system()
    if cn.button("❌ NO, CANCEL", use_container_width=True):
        st.session_state.confirm_reset = False
        st.rerun()