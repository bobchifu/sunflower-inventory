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

st.markdown("""
    <style>
    @import url('https://fonts.googleapis.com/css2?family=Inter:wght@400;700;800&display=swap');
    html, body, [class*="css"] { font-family: 'Inter', sans-serif; }
    .main-header { text-align: center; padding: 10px; margin-bottom: 20px; }
    .header-text {
        font-family: 'Inter', sans-serif; font-weight: 800; font-size: 42px;
        letter-spacing: 2px; color: #1E1E1E; margin-top: -10px; text-transform: uppercase;
    }
    div[data-baseweb="tab-list"] { gap: 20px; justify-content: center; }
    div[data-baseweb="tab"] {
        background-color: #f0f2f6; border-radius: 12px; padding: 12px 30px !important;
        font-weight: 700; border: 1px solid #ddd; min-width: 200px; text-align: center;
    }
    div[data-baseweb="tab"][aria-selected="true"] {
        background-color: #1E1E1E !important; color: white !important;
    }
    </style>
    """, unsafe_allow_html=True)

# --- DATABASE ENGINE ---
DB_NAME = 'sunflower_pro_v11.db'

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

# --- RESET FUNCTION ---
def reset_system():
    c = conn.cursor()
    c.execute("DELETE FROM inventory")
    conn.commit()
    st.cache_data.clear()
    st.success("System Reset! All data has been cleared.")

# --- SIDEBAR HOME/RESET BUTTON ---
with st.sidebar:
    st.image("logo.png") if os.path.exists("logo.png") else None
    st.title("Settings")
    if st.button("🏠 Home / Reset Everything"):
        # We use a double confirmation to prevent accidental clicks
        st.session_state.confirm_reset = True

    if st.session_state.get('confirm_reset'):
        st.warning("Are you sure? This will wipe ALL current stock data.")
        if st.button("Yes, Clear Everything"):
            reset_system()
            del st.session_state.confirm_reset
            st.rerun()
        if st.button("Cancel"):
            del st.session_state.confirm_reset
            st.rerun()

# --- HEADER ---
col_l, col_m, col_r = st.columns([1, 1, 1])
with col_m:
    if os.path.exists("logo.png"):
        st.image("logo.png", use_container_width=True)
st.markdown('<div class="main-header"><h1 class="header-text">SUNFLOWER LOUNGE & RESTAURANT</h1></div>', unsafe_allow_html=True)

# --- DEFAULT DATA ---
DEFAULT_PRODUCTS = [
    ("WATER", "SOFTS / BEERS"), ("HEINEKEN", "SOFTS / BEERS"), ("DESPERADO", "SOFTS / BEERS"),
    ("D/BLACK", "SOFTS / BEERS"), ("TIGER", "SOFTS / BEERS"), ("LIFE", "SOFTS / BEERS"),
    ("MALTA", "SOFTS / BEERS"), ("FAYROUZ", "SOFTS / BEERS"), ("ORIGIN BITTERS", "SOFTS / BEERS")
]

CATEGORY_MAP = {
    "SOFTS / BEERS": ["WATER", "BEER", "STOUT", "DESPERADO", "HEINEKEN", "TIGER", "LIFE", "TROPHY", "FAYROUZ", "MALTA", "COKE", "SPRITE", "FANTA", "BITTERS", "BULLET", "RADLER", "FLYING FISH", "LEGEND", "HERO", "GOLDBERG", "CASTLE", "ORIGIN", "D/BLACK"],
    "SHISHA": ["SHISHA"],
    "WINES": ["WINE", "DROSFDY", "HOF", "CHAMPAGNE"],
    "MOCKTAIL": ["CHAPMAN", "SUNRISE", "VIRGIN", "MOCKTAIL", "SWEET SUNRISE"],
    "REGULAR COOKTAIL": ["TEA", "MARTINI", "ISLAND", "COCKTAIL", "COSMOPOLITAN", "PINA", "TEQUILA", "BIKINI", "MARGARITA"]
}

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
        cat = "UNCATEGORIZED"
        for c_group, keywords in CATEGORY_MAP.items():
            if any(key in name for key in keywords):
                cat = c_group; break
        extracted.append({"name": name, "qty": qty, "category": cat})
    return extracted, report_date

# --- UI TABS ---
df_db = pd.read_sql_query("SELECT * FROM inventory", conn)
tabs = st.tabs(["📋 1. INVENTORY BALANCE", "📤 2. UPLOAD & SYNC", "📜 3. FINAL REPORT"])

# --- TAB 1: BALANCE ---
with tabs[0]:
    st.header("1. Record Physical Stock Balance")
    if df_db.empty:
        st.info("System is currently empty. Use the options below to populate your inventory.")
        c1, c2 = st.columns(2)
        if c1.button("✨ Initialize Default Product List (Qty 0)"):
            for name, cat in DEFAULT_PRODUCTS:
                conn.execute("INSERT OR IGNORE INTO inventory (name, category, manual_stock) VALUES (?,?,0)", (name, cat))
            conn.commit()
            st.rerun()
        
        stock_file = c2.file_uploader("Upload Initial Stock Report (.pdf, .xps, .csv)", type=["pdf", "xps", "csv"], key="init_stock")
        if stock_file:
            items, r_date = process_report(stock_file)
            if items and st.button("🚀 Set as Initial Balance"):
                for item in items:
                    conn.execute("""INSERT INTO inventory (name, category, manual_stock, last_updated) VALUES (?,?,?,?)
                                 ON CONFLICT(name) DO UPDATE SET manual_stock=excluded.manual_stock""", (item['name'], item['category'], item['qty'], r_date))
                conn.commit()
                st.rerun()
    else:
        st.subheader("Current Stock Table (Editable)")
        edited_df = st.data_editor(
            df_db[["category", "name", "manual_stock", "reorder_level"]],
            use_container_width=True, hide_index=True, key="manual_editor"
        )
        if st.button("💾 Save Changes"):
            for _, row in edited_df.iterrows():
                conn.execute("UPDATE inventory SET manual_stock=?, reorder_level=? WHERE name=?", (row['manual_stock'], row['reorder_level'], row['name']))
            conn.commit()
            st.success("Changes saved!")

# --- TAB 2: UPLOAD SALES ---
with tabs[1]:
    st.header("2. Deduct Sales from Balance")
    sales_file = st.file_uploader("Upload Daily Sales Report (.pdf, .xps, .csv)", type=["pdf", "xps", "csv"], key="sales_sync")
    if sales_file:
        sales_items, r_date = process_report(sales_file)
        if sales_items:
            st.write(f"📅 Report Date: {r_date}")
            st.dataframe(pd.DataFrame(sales_items), use_container_width=True)
            if st.button("➖ Process & Deduct Sales"):
                for item in sales_items:
                    conn.execute("UPDATE inventory SET manual_stock = manual_stock - ?, last_sales_qty = ?, last_updated = ? WHERE name = ?", 
                                 (item['qty'], item['qty'], r_date, item['name']))
                conn.commit()
                st.success("Sales Deducted!")
                st.rerun()

# --- TAB 3: FINAL REPORT ---
with tabs[2]:
    st.header("3. Movement & Restock")
    if not df_db.empty:
        report_df = df_db.copy()
        report_df['Opening'] = report_df['manual_stock'] + report_df['last_sales_qty']
        st.dataframe(
            report_df[["category", "name", "Opening", "last_sales_qty", "manual_stock", "last_updated"]],
            column_config={"Opening": "Start Bal", "last_sales_qty": "Sold", "manual_stock": "Current Bal"},
            use_container_width=True, hide_index=True
        )
    else:
        st.info("No data recorded.")

conn.close()