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

    div[data-baseweb="tab-list"] { gap: 20px; justify-content: center; background-color: transparent; }
    div[data-baseweb="tab"] {
        background-color: #f0f2f6; border-radius: 12px; padding: 12px 30px !important;
        font-weight: 700; border: 1px solid #ddd; min-width: 200px; text-align: center;
    }
    div[data-baseweb="tab"][aria-selected="true"] {
        background-color: #1E1E1E !important; color: white !important;
        box-shadow: 0 4px 15px rgba(0,0,0,0.2);
    }
    </style>
    """, unsafe_allow_html=True)

# --- DATABASE ENGINE ---
DB_NAME = 'sunflower_pro_v13.db'

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
    st.rerun()

# --- HEADER ---
col_l, col_m, col_r = st.columns([1, 1, 1])
with col_m:
    if os.path.exists("logo.png"):
        st.image("logo.png", use_container_width=True)

st.markdown('<div class="main-header"><h1 class="header-text">SUNFLOWER LOUNGE & RESTAURANT</h1></div>', unsafe_allow_html=True)

# --- CATEGORY BRAIN ---
CATEGORY_MAP = {
    "SOFTS / BEERS": ["WATER", "BEER", "STOUT", "DESPERADO", "HEINEKEN", "TIGER", "LIFE", "TROPHY", "FAYROUZ", "MALTA", "COKE", "SPRITE", "FANTA", "BITTERS", "BULLET", "RADLER", "FLYING FISH", "LEGEND", "HERO", "GOLDBERG", "CASTLE", "ORIGIN", "D/BLACK"],
    "SHISHA": ["SHISHA"], "WINES": ["WINE", "DROSFDY", "HOF", "CHAMPAGNE"],
    "MOCKTAIL": ["CHAPMAN", "SUNRISE", "VIRGIN", "MOCKTAIL", "SWEET SUNRISE"]
}

# --- UNIVERSAL PARSING ENGINE ---
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

# --- APP LOGIC ---
df_db = pd.read_sql_query("SELECT * FROM inventory", conn)
tabs = st.tabs(["📋 1. INVENTORY BALANCE", "📤 2. UPLOAD & SYNC", "📜 3. FINAL REPORT"])

# --- TAB 1: BALANCE ---
with tabs[0]:
    st.header("Step 1: Record Opening Balance")
    if df_db.empty:
        st.info("Inventory is empty. Setup your stock manually or upload an initial report.")
        c1, c2 = st.columns(2)
        if c1.button("✨ Initialize Common Products (Qty 0)"):
            for name, cat in [("WATER", "SOFTS / BEERS"), ("HEINEKEN", "SOFTS / BEERS")]:
                conn.execute("INSERT OR IGNORE INTO inventory (name, category, manual_stock) VALUES (?,?,0)", (name, cat))
            conn.commit()
            st.rerun()
        
        up_stock = c2.file_uploader("Upload Initial Stock Report", type=["pdf", "xps", "csv"], key="init_up")
        if up_stock:
            items, r_date = process_report(up_stock)
            if items and st.button("🚀 Set as Initial Balance"):
                for item in items:
                    conn.execute("""INSERT INTO inventory (name, category, manual_stock, last_updated) VALUES (?,?,?,?)
                                 ON CONFLICT(name) DO UPDATE SET manual_stock=excluded.manual_stock""", (item['name'], item['category'], item['qty'], r_date))
                conn.commit()
                st.rerun()
    else:
        edited_df = st.data_editor(df_db[["category", "name", "manual_stock", "reorder_level"]], use_container_width=True, hide_index=True)
        if st.button("💾 Save All Changes"):
            for _, row in edited_df.iterrows():
                conn.execute("UPDATE inventory SET manual_stock=?, reorder_level=? WHERE name=?", (row['manual_stock'], row['reorder_level'], row['name']))
            conn.commit()
            st.success("Changes saved!")

# --- TAB 2: UPLOAD SALES ---
with tabs[1]:
    st.header("Step 2: Deduct Daily Sales")
    sales_file = st.file_uploader("Upload Sales Report", type=["pdf", "xps", "csv"], key="sale_up")
    if sales_file:
        sales_items, r_date = process_report(sales_file)
        if sales_items:
            st.write(f"📅 Report Date: {r_date}")
            st.dataframe(pd.DataFrame(sales_items), use_container_width=True)
            if st.button("➖ Deduct Sales"):
                for item in sales_items:
                    conn.execute("UPDATE inventory SET manual_stock = manual_stock - ?, last_sales_qty = ?, last_updated = ? WHERE name = ?", 
                                 (item['qty'], item['qty'], r_date, item['name']))
                conn.commit()
                st.success("Sales Deducted!")
                st.rerun()

# --- TAB 3: FINAL REPORT & EXPORT ---
with tabs[2]:
    st.header("Step 3: Stock Movement Report")
    if not df_db.empty:
        report_df = df_db.copy()
        report_df['Opening'] = report_df['manual_stock'] + report_df['last_sales_qty']
        st.dataframe(
            report_df[["category", "name", "Opening", "last_sales_qty", "manual_stock", "last_updated"]],
            column_config={"Opening": "Start Bal", "last_sales_qty": "Sold", "manual_stock": "Current Bal"},
            use_container_width=True, hide_index=True
        )

        st.markdown("---")
        st.subheader("📥 Export Official Report")
        
        if st.button("📝 Generate PDF Report"):
            pdf = FPDF()
            pdf.add_page()
            
            # Center Logo
            if os.path.exists("logo.png"):
                # Page width is 210mm. To center a 40mm image: (210 - 40) / 2 = 85
                pdf.image("logo.png", x=85, y=10, w=40)
                pdf.ln(45) # Space after logo
            
            pdf.set_font("Arial", 'B', 16)
            pdf.cell(190, 10, "SUNFLOWER LOUNGE & RESTAURANT", ln=True, align='C')
            pdf.set_font("Arial", 'B', 12)
            pdf.cell(190, 10, "INVENTORY MOVEMENT REPORT", ln=True, align='C')
            pdf.set_font("Arial", '', 10)
            pdf.cell(190, 10, f"Date: {datetime.now().strftime('%d %b %Y %H:%M')}", ln=True, align='C')
            pdf.ln(10)

            # Table Header
            pdf.set_fill_color(30, 30, 30)
            pdf.set_text_color(255, 255, 255)
            pdf.cell(80, 10, " Product", border=1, fill=True)
            pdf.cell(40, 10, " Start Bal", border=1, fill=True)
            pdf.cell(30, 10, " Sold", border=1, fill=True)
            pdf.cell(40, 10, " Current Bal", border=1, fill=True, ln=True)

            # Table Body
            pdf.set_text_color(0, 0, 0)
            for _, row in report_df.iterrows():
                pdf.cell(80, 10, f" {row['name']}", border=1)
                pdf.cell(40, 10, f" {row['Opening']}", border=1)
                pdf.cell(30, 10, f" {row['last_sales_qty']}", border=1)
                pdf.cell(40, 10, f" {row['manual_stock']}", border=1, ln=True)

            pdf_data = pdf.output(dest='S').encode('latin-1')
            st.download_button(
                label="📥 Download PDF Now",
                data=pdf_data,
                file_name=f"sunflower_report_{datetime.now().strftime('%Y%m%d')}.pdf",
                mime="application/pdf"
            )
    else:
        st.info("No data available to generate a report.")

# --- FOOTER RESET ---
st.markdown("---")
if st.button("🏠 Home / Reset System", use_container_width=True):
    st.session_state.confirm_wipe = True

if st.session_state.get('confirm_wipe'):
    st.error("Wipe all data?")
    ca, cb = st.columns(2)
    if ca.button("✅ YES"): 
        reset_database()
        del st.session_state.confirm_wipe
    if cb.button("❌ NO"): 
        del st.session_state.confirm_wipe
        st.rerun()

conn.close()