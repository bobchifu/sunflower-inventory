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
DB_NAME = 'sunflower_pro_v15.db'

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
    # Reset states
    st.session_state.current_step = 0
    st.session_state.confirm_wipe = False
    st.rerun()

# --- HEADER ---
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
    if file.name.lower().endswith(('.pdf', '.xps')):
        doc = fitz.open(stream=file.read(), filetype=file.name.split('.')[-1].lower())
        for page in doc: raw_text += page.get_text() + "\n"
    else:
        raw_text = file.getvalue().decode("utf-8").replace('"', '')
    
    date_match = re.findall(r"(\d{1,2}\s+[A-Za-z]+\s+\d{4}\s+\d{2}:\d{2})", raw_text)
    report_date = date_match[-1] if date_match else datetime.now().strftime("%d %b %Y %H:%M")
    product_pattern = re.compile(r"^(.+?)\s+(\d+)\s+([\d,]+\.\d{2})$", re.MULTILINE)
    matches = product_pattern.findall(raw_text)
    extracted = []
    for m in matches:
        name = m[0].strip().upper()
        qty = int(m[1])
        if "TOTAL" in name or "SNOOKER" in name: continue
        extracted.append({"name": name, "qty": qty})
    return extracted, report_date

# --- LOAD DATA ---
df_db = pd.read_sql_query("SELECT * FROM inventory", conn)

# --- STEP 1: BALANCE ---
if st.session_state.current_step == 0:
    st.header("Step 1: Record Opening Balance")
    
    if df_db.empty:
        st.info("The system is empty. Initialize common products or upload a report.")
        c1, c2 = st.columns(2)
        if c1.button("✨ Initialize Common Products (Qty 0)"):
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
            if items and st.button("🚀 Confirm Initial Stock"):
                for item in items:
                    conn.execute("INSERT INTO inventory (name, manual_stock, last_updated) VALUES (?,?,?) ON CONFLICT(name) DO UPDATE SET manual_stock=excluded.manual_stock", (item['name'], item['qty'], r_date))
                conn.commit()
                st.rerun()
    
    # Editable and DYNAMIC table (can add rows)
    st.subheader("Inventory Table")
    st.caption("Double click the bottom row to add new products manually.")
    edited_df = st.data_editor(
        df_db[["category", "name", "manual_stock", "reorder_level"]], 
        use_container_width=True, 
        hide_index=True, 
        num_rows="dynamic" # THIS ALLOWS ADDING ROWS
    )
    
    if st.button("💾 Save All Changes", use_container_width=True):
        # Clear old and save new state to handle added/deleted rows
        conn.execute("DELETE FROM inventory")
        for _, row in edited_df.iterrows():
            if pd.notna(row['name']) and str(row['name']).strip() != "":
                conn.execute("INSERT OR IGNORE INTO inventory (category, name, manual_stock, reorder_level) VALUES (?,?,?,?)",
                             (row['category'], row['name'].upper(), row['manual_stock'], row['reorder_level']))
        conn.commit()
        st.success("Database Saved!")
        st.rerun()
    
    if not df_db.empty:
        if st.button("➡️ NEXT STEP: UPLOAD SALES", use_container_width=True):
            st.session_state.current_step = 1
            st.rerun()

# --- STEP 2: UPLOAD SALES ---
elif st.session_state.current_step == 1:
    st.header("Step 2: Deduct Daily Sales")
    sales_file = st.file_uploader("Upload Sales Report", type=["pdf", "xps", "csv"])
    if sales_file:
        sales_items, r_date = process_report(sales_file)
        if sales_items:
            st.write(f"📅 Report Date: {r_date}")
            st.dataframe(pd.DataFrame(sales_items), use_container_width=True)
            if st.button("➖ Deduct Sales", use_container_width=True):
                for item in sales_items:
                    conn.execute("UPDATE inventory SET manual_stock = manual_stock - ?, last_sales_qty = ?, last_updated = ? WHERE name = ?", 
                                 (item['qty'], item['qty'], r_date, item['name']))
                conn.commit()
                st.success("Sales Deducted!")
            
            if st.button("➡️ NEXT STEP: VIEW FINAL REPORT", use_container_width=True):
                st.session_state.current_step = 2
                st.rerun()

# --- STEP 3: FINAL REPORT ---
elif st.session_state.current_step == 2:
    st.header("Step 3: Final Inventory Report")
    if not df_db.empty:
        report_df = df_db.copy()
        report_df['Opening'] = report_df['manual_stock'] + report_df['last_sales_qty']
        st.dataframe(
            report_df[["category", "name", "Opening", "last_sales_qty", "manual_stock", "last_updated"]],
            column_config={"Opening": "Start Bal", "last_sales_qty": "Sold", "manual_stock": "Current Bal"},
            use_container_width=True, hide_index=True
        )
        
        st.markdown("---")
        if st.button("📝 Generate PDF Report", use_container_width=True):
            pdf = FPDF()
            pdf.add_page()
            if os.path.exists("logo.png"):
                pdf.image("logo.png", x=85, y=10, w=40)
                pdf.ln(45)
            pdf.set_font("Arial", 'B', 16)
            pdf.cell(190, 10, "SUNFLOWER LOUNGE & RESTAURANT", ln=True, align='C')
            pdf.ln(10)
            pdf.set_fill_color(200, 200, 200)
            pdf.cell(80, 10, " Product", border=1, fill=True)
            pdf.cell(30, 10, " Start", border=1, fill=True)
            pdf.cell(30, 10, " Sold", border=1, fill=True)
            pdf.cell(50, 10, " Balance", border=1, fill=True, ln=True)
            for _, row in report_df.iterrows():
                pdf.cell(80, 10, str(row['name']), border=1)
                pdf.cell(30, 10, str(row['Opening']), border=1)
                pdf.cell(30, 10, str(row['last_sales_qty']), border=1)
                pdf.cell(50, 10, str(row['manual_stock']), border=1, ln=True)
            st.download_button("📥 Download PDF Now",