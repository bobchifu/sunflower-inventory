import streamlit as st
import pandas as pd
import sqlite3
import pdfplumber
import re
from datetime import datetime
from fpdf import FPDF
import os

# --- CONFIG & STYLING ---
st.set_page_config(page_title="SUNFLOWER LOUNGE INVENTORY SYSTEM", layout="wide")

# Custom CSS for the "Inter" font and centralized header
st.markdown("""
    <style>
    @import url('https://fonts.googleapis.com/css2?family=Inter:wght@400;700;800&display=swap');
    
    html, body, [class*="css"] {
        font-family: 'Inter', sans-serif;
    }
    
    .main-header {
        text-align: center;
        padding: 10px;
        margin-bottom: 20px;
    }
    
    .header-text {
        font-family: 'Inter', sans-serif;
        font-weight: 800;
        font-size: 42px;
        letter-spacing: 2px;
        color: #1E1E1E;
        margin-top: -10px;
    }
    
    .stMetric {
        background-color: #ffffff;
        padding: 20px;
        border-radius: 10px;
        border: 1px solid #eee;
    }
    </style>
    """, unsafe_allow_html=True)

# --- HEADER SECTION (LOGO & NAME) ---
# Create 3 columns to center the logo
col_l, col_m, col_r = st.columns([1, 1, 1])

with col_m:
    # Check if logo exists before showing
    if os.path.exists("logo.png"):
        st.image("logo.png", use_container_width=True)
    else:
        st.warning("Save your logo as 'logo.png' in the app folder to see it here.")

st.markdown('<div class="main-header"><h1 class="header-text">SUNFLOWER LOUNGE & RESTAURANT</h1></div>', unsafe_allow_html=True)

# --- DATABASE ENGINE ---
def init_db():
    conn = sqlite3.connect('sunflower_v8.db', check_same_thread=False)
    c = conn.cursor()
    c.execute('''CREATE TABLE IF NOT EXISTS inventory 
                 (id INTEGER PRIMARY KEY, name TEXT UNIQUE, category TEXT, 
                  manual_stock INTEGER DEFAULT 0, last_sales_qty INTEGER DEFAULT 0,
                  reorder_level INTEGER DEFAULT 5, last_updated TEXT)''')
    conn.commit()
    return conn

conn = init_db()

# --- CATEGORY BRAIN ---
CATEGORY_MAP = {
    "SOFTS / BEERS": ["WATER", "BEER", "STOUT", "DESPERADO", "HEINEKEN", "TIGER", "LIFE", "TROPHY", "FAYROUZ", "MALTA", "COKE", "SPRITE", "FANTA", "BITTERS", "BULLET", "RADLER", "FLYING FISH", "LEGEND", "HERO", "GOLDBERG", "CASTLE", "ORIGIN", "D/BLACK"],
    "SHISHA": ["SHISHA"],
    "WINES": ["WINE", "DROSFDY", "HOF", "CHAMPAGNE"],
    "MOCKTAIL": ["CHAPMAN", "SUNRISE", "VIRGIN", "MOCKTAIL", "SWEET SUNRISE"],
    "REGULAR COOKTAIL": ["TEA", "MARTINI", "ISLAND", "COCKTAIL", "COSMOPOLITAN", "PINA", "TEQUILA", "BIKINI", "MARGARITA"],
    "MILK SHAKERS": ["SHAKE", "OREO", "VANILLA", "MILKSHAKE"],
    "SMOOTHIE": ["SMOOTHIE", "BANANA", "PINEAPPLE", "YOGHURT"],
    "LEMONADE/ICE TEA": ["LEMONADE", "ICE TEA"]
}

# --- PARSING ENGINE ---
def process_report(file):
    raw_text = ""
    if file.name.endswith('.pdf'):
        with pdfplumber.open(file) as pdf:
            raw_text = "\n".join([p.extract_text() for p in pdf.pages if p.extract_text()])
    else:
        raw_text = file.getvalue().decode("utf-8").replace('"', '')

    date_match = re.findall(r"(\d{1,2}\s+[A-Za-z]+\s+\d{4}\s+\d{2}:\d{2})", raw_text)
    report_date = date_match[-1] if date_match else datetime.now().strftime("%d %b %Y %H:%M")

    product_pattern = re.compile(r"^(.+?)\s+(\d+)\s+([\d,]+\.\d{2})$", re.MULTILINE)
    matches = product_pattern.findall(raw_text)
    
    extracted_items = []
    for m in matches:
        name = m[0].strip().upper()
        qty = int(m[1])
        if "TOTAL" in name or "SNOOKER" in name: continue
        
        cat = "UNCATEGORIZED"
        for c_group, keywords in CATEGORY_MAP.items():
            if any(key in name for key in keywords):
                cat = c_group; break
        extracted_items.append({"name": name, "qty": qty, "category": cat})
    return extracted_items, report_date

# --- UI TAB LOGIC ---
df_db = pd.read_sql_query("SELECT * FROM inventory", conn)
tabs = st.tabs(["📋 1. Physical Stock Balance", "📤 2. Upload & Deduct Sales", "📜 3. Final Report"])

# --- TAB 1: PHYSICAL STOCK ---
with tabs[0]:
    st.header("Step 1: Record Current Physical Stock")
    col_a, col_b = st.columns([1, 1])
    
    with col_a:
        st.subheader("Option A: Manual Entry")
        if not df_db.empty:
            edited_df = st.data_editor(
                df_db[["id", "category", "name", "manual_stock", "reorder_level"]],
                column_order=("category", "name", "manual_stock", "reorder_level"),
                disabled=("name",), use_container_width=True, hide_index=True, key="manual_editor"
            )
            if st.button("💾 Save Manual Edits"):
                for _, row in edited_df.iterrows():
                    conn.execute("UPDATE inventory SET category=?, manual_stock=?, reorder_level=? WHERE id=?",
                                 (row['category'], row['manual_stock'], row['reorder_level'], row['id']))
                conn.commit()
                st.success("Manual stock updated!")
                st.rerun()

    with col_b:
        st.subheader("Option B: Upload Stock Report")
        stock_file = st.file_uploader("Upload .pdf or .csv Stock Report", type=["pdf", "csv"], key="stock_up")
        if stock_file:
            items, r_date = process_report(stock_file)
            if items and st.button("🚀 Set as Opening Physical Stock"):
                for item in items:
                    conn.execute("""INSERT INTO inventory (name, category, manual_stock, last_updated) 
                                 VALUES (?, ?, ?, ?)
                                 ON CONFLICT(name) DO UPDATE SET manual_stock=excluded.manual_stock, last_updated=excluded.last_updated""",
                                 (item['name'], item['category'], item['qty'], r_date))
                conn.commit()
                st.success("Database populated from report!")
                st.rerun()

# --- TAB 2: SALES DEDUCTION ---
with tabs[1]:
    st.header("Step 2: Upload Sales Report")
    sales_file = st.file_uploader("Upload Daily Sales Report", type=["pdf", "csv"], key="sales_up")
    if sales_file:
        sales_items, r_date = process_report(sales_file)
        if sales_items:
            st.write(f"📅 Sales Report Date: {r_date}")
            st.dataframe(pd.DataFrame(sales_items), use_container_width=True)
            if st.button("➖ Process Sales Deductions"):
                for item in sales_items:
                    conn.execute("""UPDATE inventory SET 
                                 manual_stock = manual_stock - ?, 
                                 last_sales_qty = ?, 
                                 last_updated = ? 
                                 WHERE name = ?""", (item['qty'], item['qty'], r_date, item['name']))
                conn.commit()
                st.success("Sales deducted from Opening Balance!")
                st.rerun()

# --- TAB 3: FINAL REPORT ---
with tabs[2]:
    st.header("Step 3: Final Inventory Movement")
    if not df_db.empty:
        report_df = df_db.copy()
        report_df['Opening_Bal'] = report_df['manual_stock'] + report_df['last_sales_qty']
        
        st.dataframe(
            report_df[["category", "name", "Opening_Bal", "last_sales_qty", "manual_stock", "last_updated"]],
            column_config={
                "category": "Group", "name": "Product", 
                "Opening_Bal": "Opening Balance", "last_sales_qty": "Total Sold", 
                "manual_stock": "Current Balance", "last_updated": "As Of"
            }, use_container_width=True, hide_index=True
        )

        st.markdown("---")
        st.subheader("📋 Restock Purchase Order")
        restock = report_df[report_df['manual_stock'] <= report_df['reorder_level']].copy()
        if not restock.empty:
            restock['To_Order'] = (restock['reorder_level'] * 5) - restock['manual_stock']
            st.table(restock[["category", "name", "manual_stock", "To_Order"]])
            
            if st.button("📥 Download PO"):
                pdf = FPDF()
                pdf.add_page()
                pdf.set_font("Arial", 'B', 16)
                pdf.cell(190, 10, "SUNFLOWER RESTOCK ORDER", ln=True, align='C')
                pdf.ln(10)
                for _, row in restock.iterrows():
                    pdf.cell(100, 10, str(row['name']), border=1)
                    pdf.cell(90, 10, f"Order Qty: {row['To_Order']}", border=1, ln=True)
                st.download_button("Download PDF", data=pdf.output(dest='S').encode('latin-1'), file_name="order.pdf")
    else:
        st.info("No data available.")

conn.close()