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
    .stMetric { background-color: #ffffff; padding: 20px; border-radius: 10px; border: 1px solid #eee; }
    </style>
    """, unsafe_allow_html=True)

# --- HEADER SECTION (LOGO & NAME) ---
col_l, col_m, col_r = st.columns([1, 1, 1])
with col_m:
    if os.path.exists("logo.png"):
        st.image("logo.png", use_container_width=True)
st.markdown('<div class="main-header"><h1 class="header-text">SUNFLOWER LOUNGE & RESTAURANT</h1></div>', unsafe_allow_html=True)

# --- DATABASE ENGINE ---
def init_db():
    conn = sqlite3.connect('sunflower_pro_v9.db', check_same_thread=False)
    c = conn.cursor()
    c.execute('''CREATE TABLE IF NOT EXISTS inventory 
                 (id INTEGER PRIMARY KEY, name TEXT UNIQUE, category TEXT, 
                  manual_stock INTEGER DEFAULT 0, last_sales_qty INTEGER DEFAULT 0,
                  reorder_level INTEGER DEFAULT 5, last_updated TEXT)''')
    conn.commit()
    return conn

conn = init_db()

# --- PRE-DEFINED PRODUCT LIST (Based on your reports) ---
DEFAULT_PRODUCTS = [
    ("WATER", "SOFTS / BEERS"), ("HEINEKEN", "SOFTS / BEERS"), ("DESPERADO", "SOFTS / BEERS"),
    ("D/BLACK", "SOFTS / BEERS"), ("TIGER", "SOFTS / BEERS"), ("LIFE", "SOFTS / BEERS"),
    ("MALTA", "SOFTS / BEERS"), ("FAYROUZ", "SOFTS / BEERS"), ("ORIGIN BITTERS", "SOFTS / BEERS"),
    ("BUDWEISER", "SOFTS / BEERS"), ("TROPHY", "SOFTS / BEERS"), ("BLACK BULLET", "SOFTS / BEERS"),
    ("SHISHA BIG", "SHISHA"), ("SHISHA MEDIUM", "SHISHA"), ("SHISHA SMALL", "SHISHA"),
    ("CHAPMAN", "MOCKTAIL"), ("SWEET SUNRISE", "MOCKTAIL"), ("VANILLA MILKSHAKE", "MILK SHAKERS"),
    ("OREO MILK SHAKE", "MILK SHAKERS"), ("LONG ISLAND TEA", "REGULAR COOKTAIL"),
    ("PINA COLADA", "REGULAR COOKTAIL"), ("ICE TEA", "LEMONADE/ICE TEA")
]

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

# --- UNIVERSAL PARSING ENGINE (PDF, XPS, CSV) ---
def process_report(file):
    raw_text = ""
    # Handle PDF and XPS
    if file.name.lower().endswith(('.pdf', '.xps')):
        doc = fitz.open(stream=file.read(), filetype=file.name.split('.')[-1].lower())
        for page in doc:
            raw_text += page.get_text() + "\n"
    # Handle CSV
    else:
        raw_text = file.getvalue().decode("utf-8").replace('"', '')

    # Extract Date
    date_match = re.findall(r"(\d{1,2}\s+[A-Za-z]+\s+\d{4}\s+\d{2}:\d{2})", raw_text)
    report_date = date_match[-1] if date_match else datetime.now().strftime("%d %b %Y %H:%M")

    # Regex: Product Name | Quantity | Amount
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

# --- UI LOGIC ---
df_db = pd.read_sql_query("SELECT * FROM inventory", conn)
tabs = st.tabs(["📋 1. Inventory Balance", "📤 2. Upload Sales (Deduct)", "📜 3. Final Report"])

# --- TAB 1: INVENTORY BALANCE ---
with tabs[0]:
    st.header("Step 1: Current Physical Stock")
    
    if df_db.empty:
        st.warning("No products found in the database.")
        col1, col2 = st.columns(2)
        if col1.button("✨ Initialize Default Product List (Qty 0)"):
            for name, cat in DEFAULT_PRODUCTS:
                conn.execute("INSERT OR IGNORE INTO inventory (name, category, manual_stock) VALUES (?,?,0)", (name, cat))
            conn.commit()
            st.rerun()
        st.write("OR")
        stock_file = col2.file_uploader("Upload .pdf, .xps or .csv to load full stock", type=["pdf", "xps", "csv"])
        if stock_file:
            items, r_date = process_report(stock_file)
            if items and st.button("🚀 Load these as Starting Physical Stock"):
                for item in items:
                    conn.execute("""INSERT INTO inventory (name, category, manual_stock, last_updated) VALUES (?,?,?,?)
                                 ON CONFLICT(name) DO UPDATE SET manual_stock=excluded.manual_stock""", (item['name'], item['category'], item['qty'], r_date))
                conn.commit()
                st.rerun()
    else:
        st.write("Edit the 'Manual Stock' column to reflect what is currently on the shelves.")
        edited_df = st.data_editor(
            df_db[["category", "name", "manual_stock", "reorder_level"]],
            use_container_width=True, hide_index=True, key="bal_editor"
        )
        if st.button("💾 Save All Stock Changes"):
            for _, row in edited_df.iterrows():
                conn.execute("UPDATE inventory SET manual_stock=?, reorder_level=? WHERE name=?", 
                             (row['manual_stock'], row['reorder_level'], row['name']))
            conn.commit()
            st.success("Physical stock updated!")

# --- TAB 2: UPLOAD SALES ---
with tabs[1]:
    st.header("Step 2: Upload Sales Report")
    st.write("The system will deduct these sales from your Physical Stock balance.")
    sales_file = st.file_uploader("Choose Sales Report (.pdf, .xps, .csv)", type=["pdf", "xps", "csv"])
    if sales_file:
        sales_items, r_date = process_report(sales_file)
        if sales_items:
            st.write(f"📅 Sales Report Date: {r_date}")
            st.dataframe(pd.DataFrame(sales_items), use_container_width=True)
            if st.button("➖ Process & Deduct Sales"):
                for item in sales_items:
                    conn.execute("UPDATE inventory SET manual_stock = manual_stock - ?, last_sales_qty = ?, last_updated = ? WHERE name = ?", 
                                 (item['qty'], item['qty'], r_date, item['name']))
                conn.commit()
                st.success("Sales successfully deducted!")
                st.rerun()

# --- TAB 3: FINAL REPORT ---
with tabs[2]:
    st.header("Step 3: Final Inventory Report")
    if not df_db.empty:
        report_df = df_db.copy()
        report_df['Opening'] = report_df['manual_stock'] + report_df['last_sales_qty']
        
        st.subheader("Inventory Movement Summary")
        st.dataframe(
            report_df[["category", "name", "Opening", "last_sales_qty", "manual_stock", "last_updated"]],
            column_config={
                "category": "Group", "Opening": "Start Bal", 
                "last_sales_qty": "Sold", "manual_stock": "Closing Bal"
            }, use_container_width=True, hide_index=True
        )

        st.markdown("---")
        st.subheader("📋 Restock Purchase Order")
        low = report_df[report_df['manual_stock'] <= report_df['reorder_level']].copy()
        if not low.empty:
            low['Order'] = (low['reorder_level'] * 5) - low['manual_stock']
            st.table(low[["category", "name", "manual_stock", "Order"]])
            if st.button("📥 Download PO"):
                pdf = FPDF()
                pdf.add_page(); pdf.set_font("Arial", 'B', 16)
                pdf.cell(190, 10, "SUNFLOWER RESTOCK ORDER", ln=True, align='C')
                for _, row in low.iterrows():
                    pdf.cell(100, 10, str(row['name']), border=1)
                    pdf.cell(90, 10, f"Order: {row['Order']}", border=1, ln=True)
                st.download_button("Download PDF", data=pdf.output(dest='S').encode('latin-1'), file_name="order.pdf")
    else:
        st.info("No data recorded yet.")

conn.close()