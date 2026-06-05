# NOTE: Before running this app, make sure to install dependencies:
# pip install -r requirements.txt

import streamlit as st
import os
import json
from PIL import Image
import tempfile
import subprocess
import sys
import pandas as pd
import plotly.express as px
import openai
import base64
import io
import csv
from datetime import datetime
from process_receipt import process_receipt
from export_utils import export_to_csv, export_to_excel, export_to_pdf
import hashlib # Import hashlib for image hashing
import os.path
from auth_pages import show_login_page, show_register_page
from models import Session, User, Receipt, Budget

st.set_page_config(page_title="Receipt NoteTaker", layout="wide")

# Set OpenAI API key
openai.api_key = os.environ.get("OPENAI_API_KEY")
from session_utils import create_session, get_session, delete_session

# Initialize session state variables
if 'authenticated' not in st.session_state:
    st.session_state['authenticated'] = False
if 'show_register' not in st.session_state:
    st.session_state['show_register'] = False
if 'user_email' not in st.session_state:
    st.session_state['user_email'] = None

# Restore session from URL query param on refresh
if not st.session_state['authenticated']:
    token = st.query_params.get('session')
    if token:
        email = get_session(token)
        if email:
            st.session_state['authenticated'] = True
            st.session_state['user_email'] = email
            st.session_state['session_token'] = token

# Show login/register pages if not authenticated
if not st.session_state['authenticated']:
    if st.session_state['show_register']:
        show_register_page()
    else:
        show_login_page()
    st.stop()

def encode_image(image_path):
    with Image.open(image_path) as image:
        buffered = io.BytesIO()
        image.save(buffered, format="JPEG")
        img_bytes = buffered.getvalue()
        encoded_image = base64.b64encode(img_bytes).decode("utf-8")
        return encoded_image

# Function to calculate image hash (from process_receipt.py - duplicated here for app.py's needs)
def calculate_image_hash(image_content):
    """Calculate SHA256 hash of the image file content."""
    hasher = hashlib.sha256()
    hasher.update(image_content)
    return hasher.hexdigest()

# Function to load existing image hashes from the log file
def load_existing_hashes():
    log_file = "data/gpt_usage_log.csv"
    existing_hashes = set()
    if os.path.exists(log_file) and os.path.getsize(log_file) > 0: # Check if file exists and is not empty
        try:
            # Read only the 'image_hash' column
            df = pd.read_csv(log_file, usecols=["image_hash"], dtype=str)
            existing_hashes = set(df["image_hash"].dropna().unique()) # Add non-null unique hashes to set
        except pd.errors.EmptyDataError: # Handle empty file case
            st.warning(f"Log file '{log_file}' is empty.")
        except KeyError: # Handle case where 'image_hash' column is missing (e.g. old log file format)
            st.warning(f"'image_hash' column not found in '{log_file}'. Please ensure the log file is correctly formatted.")
        except Exception as e:
            st.error(f"Error reading log file {log_file}: {e}")
    return existing_hashes

# Initialize session state variables if not already present
if 'allow_duplicate_process' not in st.session_state:
    st.session_state['allow_duplicate_process'] = False

if 'file_uploader_key' not in st.session_state:
    st.session_state['file_uploader_key'] = 0

if 'uploaded_image_file' not in st.session_state:
    st.session_state['uploaded_image_file'] = None

if 'theme' not in st.session_state:
    st.session_state['theme'] = 'dark' # Default to dark theme

# Toggle button for theme
# Using a hidden radio button and custom CSS for a cleaner toggle look
st.sidebar.markdown("### Theme")

# Visual toggle button for theme (sun/moon icon)
if st.session_state['theme'] == 'light':
    toggle_label = '🌙 Switch to Dark Mode'
else:
    toggle_label = '☀️ Switch to Light Mode'

if st.sidebar.button(toggle_label, use_container_width=True, key="theme_toggle_button"):
    st.session_state['theme'] = 'dark' if st.session_state['theme'] == 'light' else 'light'
    st.rerun()

# Define themes as dictionaries
themes = {
    'dark': {
        'primary_bg': "#121212",
        'secondary_bg': "#1e1e1e",
        'card_bg': "#232323",
        'item_card_bg': "#292929",
        'text_color': "#e0e0e0",
        'primary_color': "#bb86fc",
        'accent_color_1': "#03dac6",
        'accent_color_2': "#ffb300",
        'border_color': "#bb86fc",
        'sub_border_color': "#444"
    },
    'light': {
        'primary_bg': "#ffffff",
        'secondary_bg': "#f0f2f6",
        'card_bg': "#ffffff",
        'item_card_bg': "#f8f8f8",
        'text_color': "#333333",
        'primary_color': "#6200ee",
        'accent_color_1': "#008080",
        'accent_color_2': "#cc5500",
        'border_color': "#6200ee",
        'sub_border_color': "#ccc"
    }
}

# Select current theme based on session state
current_theme = themes[st.session_state['theme']]

# Dynamically generate :root CSS variables
dynamic_root_css = ":root {\n"
for key, value in current_theme.items():
    dynamic_root_css += f"    --{key.replace('_', '-')}: {value};\n"
dynamic_root_css += "}\n"

# Define the rest of the CSS template (without :root variables and without style tags)
raw_css_template = """
    /* ── Base ── */
    html, body {
        font-family: 'Inter', 'Roboto', 'Segoe UI', Arial, sans-serif !important;
        background-color: var(--primary-bg) !important;
        color: var(--text-color) !important;
    }

    /* ── App containers ── */
    .stApp,
    [data-testid="stAppViewContainer"],
    [data-testid="stMain"],
    [data-testid="stMainBlockContainer"],
    [data-testid="stHeader"],
    .main, .block-container {
        background-color: var(--primary-bg) !important;
        color: var(--text-color) !important;
    }

    /* ── Sidebar ── */
    section[data-testid="stSidebar"] {
        background-color: var(--secondary-bg) !important;
        overflow: hidden !important;
    }

    section[data-testid="stSidebar"] > div:first-child,
    [data-testid="stSidebarContent"] {
        background-color: var(--secondary-bg) !important;
        box-sizing: border-box !important;
    }

    /* ── Transparent widget wrappers (prevent ghost dark boxes) ── */
    [data-testid="stElementContainer"],
    .element-container,
    [data-testid="stVerticalBlock"],
    [data-testid="stHorizontalBlock"] {
        background: transparent !important;
    }

    /* ── Text ── */
    p, span, li, td, th, small {
        color: var(--text-color) !important;
    }
    h1, h2, h3, h4, h5, h6 {
        font-family: 'Inter', 'Roboto', 'Segoe UI', Arial, sans-serif !important;
        color: var(--primary-color) !important;
        font-weight: 700;
        letter-spacing: 0.01em;
    }

    /* ── Radio / Checkbox labels ── */
    .stRadio label, .stCheckbox label,
    .stRadio label span, .stCheckbox label span {
        color: var(--text-color) !important;
    }

    /* ── Inputs ── */
    .stTextInput input, .stTextArea textarea,
    [data-testid="stTextInput"] input,
    [data-testid="stTextArea"] textarea {
        background-color: var(--card-bg) !important;
        color: var(--text-color) !important;
        border-color: var(--sub-border-color) !important;
        border-radius: 8px !important;
    }

    /* ── File uploader ── */
    [data-testid="stFileUploaderDropzone"],
    [data-testid="stFileUploader"] section {
        background-color: var(--card-bg) !important;
        border: 2px dashed var(--border-color) !important;
        border-radius: 10px !important;
    }
    [data-testid="stFileUploaderDropzoneInstructions"] div,
    [data-testid="stFileUploaderDropzoneInstructions"] span,
    [data-testid="stFileUploaderDropzoneInstructions"] small,
    [data-testid="stFileUploader"] small {
        color: var(--text-color) !important;
    }
    [data-testid="stFileUploader"] button {
        background-color: var(--secondary-bg) !important;
        color: var(--text-color) !important;
        border: 1px solid var(--sub-border-color) !important;
        border-radius: 6px !important;
    }

    /* ── Alerts / info boxes ── */
    [data-testid="stInfo"], [data-testid="stAlert"],
    [data-testid="stNotification"], .stAlert {
        background-color: var(--card-bg) !important;
        color: var(--text-color) !important;
        border-radius: 8px !important;
    }

    /* ── Buttons ── */
    .stButton > button {
        color: white !important;
        background: var(--primary-color) !important;
        border-radius: 8px;
        border: none;
        padding: 0.5em 1.5em;
        font-size: 1.05em;
        font-family: inherit;
        box-shadow: 0 3px 8px rgba(0,0,0,0.2);
        transition: background-color 0.2s ease;
    }
    .stButton > button:hover {
        background-color: var(--accent-color-1) !important;
    }

    /* ── Custom cards ── */
    .category-card {
        background: var(--card-bg);
        padding: 1em 1.2em;
        border-radius: 12px;
        margin-bottom: 1em;
        border: 2px solid var(--border-color);
        min-height: 120px;
        box-shadow: 0 2px 8px rgba(0,0,0,0.10);
    }
    .item-card {
        background: var(--item-card-bg);
        padding: 0.7em 1em;
        border-radius: 8px;
        margin-bottom: 0.5em;
        border: 1px solid var(--sub-border-color);
        box-shadow: 0 1px 4px rgba(0,0,0,0.08);
        text-align: left;
    }
    .item-title { color: var(--primary-color); font-size: 1.08em; font-weight: 600; }
    .item-desc  { color: var(--text-color); font-size: 0.98em; text-align: justify; }
    .item-detail { color: var(--text-color); }
    .item-qty     { color: var(--accent-color-1); }
    .item-price   { color: var(--accent-color-1); }
    .item-subtotal{ color: var(--accent-color-2); }
"""

# Combine dynamic :root with the rest of the CSS, and wrap in <style> tags
css_style = f"<style>\n{dynamic_root_css}{raw_css_template}\n</style>"

st.markdown(css_style, unsafe_allow_html=True)

st.markdown(
    f"""
    <h1 style='font-family:Inter,Roboto,Segoe UI,Arial,sans-serif; color:var(--primary-color); font-size:2.5em; margin-bottom:0.1em;'>🧾 Receipt Genie</h1>
    <div style='font-size:1.2em; color:var(--accent-color-1); margin-bottom:1.5em;'>Your Smart AI-Powered Expense Dashboard</div>
    """,
    unsafe_allow_html=True
)
st.markdown("<!-- Spacer for visual separation -->", unsafe_allow_html=True)

# Add a Reset Button at the top
if st.button("🔄 Reset App"):
    # Only reset app state, not authentication or theme
    st.session_state['file_uploader_key'] += 1  # Increment key to clear file uploader
    st.session_state['uploaded_image_file'] = None
    st.session_state['processed_result'] = None
    st.session_state['plotly_fig'] = None
    st.session_state['pie_data'] = None
    st.session_state['current_display_hash'] = None
    st.session_state['allow_duplicate_process'] = False
    st.rerun()

# Sidebar navigation
st.sidebar.markdown("---")
page = st.sidebar.radio(
    "Navigation",
    ["Dashboard", "Analytics", "Budgets"],
    key="main_nav_radio"
)

if page == "Dashboard":
    # Sidebar for image upload
    st.sidebar.markdown(
        f"""
        <div style='padding:1.2em 1em 0.5em 1em; background: var(--card-bg); border-radius: 14px; margin-bottom: 1.5em; box-shadow: 0 2px 8px rgba(0,0,0,0.10);'>
            <h3 style='color:var(--primary-color); font-family:Inter,Roboto,Segoe UI,Arial,sans-serif; margin-bottom:0.3em;'>Upload Receipt Image</h3>
            <div style='color:var(--text-color); font-size:1em; margin-bottom:0.7em;'>Select or drag a <b>JPG, JPEG, or PNG</b> receipt image.<br>
            <span style='font-size:0.95em; color:var(--sub-border-color);'>Max size: 200MB</span></div>
        </div>
        """,
        unsafe_allow_html=True
    )

    # Use a placeholder for the file uploader to enable explicit clearing
    file_uploader_placeholder = st.sidebar.empty()
    st.session_state['uploaded_image_file'] = file_uploader_placeholder.file_uploader(
        "",
        type=["jpg", "jpeg", "png"],
        label_visibility="collapsed",
        key=f"file_uploader_{st.session_state['file_uploader_key']}"
    )

    # Handle image upload and duplicate detection
    if st.session_state['uploaded_image_file'] is not None:
        image_file = st.session_state['uploaded_image_file']
        # Save uploaded image to a temp file
        with tempfile.NamedTemporaryFile(delete=False, suffix=".jpg") as tmp:
            tmp.write(image_file.read())
            tmp_path = tmp.name

        st.sidebar.image(tmp_path, caption="Uploaded Receipt", use_container_width=True)

        current_image_hash = calculate_image_hash(image_file.getvalue())
        existing_hashes = load_existing_hashes()

        # Determine if we need to process the receipt
        should_process_this_image = False
        
        # Condition 1: Image hash in session state is different from current image hash
        # This means a new image has been uploaded or a new instance of an old image.
        if 'current_display_hash' not in st.session_state or st.session_state['current_display_hash'] != current_image_hash:
            # Check for duplicates if it's a new or re-uploaded image not yet processed in this run
            if current_image_hash in existing_hashes and not st.session_state['allow_duplicate_process']:
                st.warning("This receipt has already been uploaded.")
                col_dup1, col_dup2 = st.columns(2)
                with col_dup1:
                    if st.button("Go ahead anyway", key="go_ahead_button"):
                        st.session_state['allow_duplicate_process'] = True
                        st.rerun() # Rerun to bypass duplicate check and process
                with col_dup2:
                    if st.button("Quit", key="quit_button"):
                        current_theme_setting = st.session_state.get('theme', 'dark')
                        st.session_state['file_uploader_key'] += 1
                        st.session_state.clear()
                        st.session_state['theme'] = current_theme_setting
                        st.rerun()
                # Stop execution here if it's a duplicate and user hasn't clicked "Go ahead anyway"
                st.stop()
            else:
                # Not a duplicate OR user clicked "Go ahead anyway" for this specific image
                should_process_this_image = True
                # Reset allow_duplicate_process after confirming we will process
                if st.session_state['allow_duplicate_process']:
                    st.session_state['allow_duplicate_process'] = False
        # Condition 2: If the image hash is the same, but processed_result is not yet set (e.g., first run after upload)
        elif 'processed_result' not in st.session_state or st.session_state['processed_result'] is None:
            should_process_this_image = True

        if should_process_this_image:
            with st.spinner("Processing receipt..."):
                try:
                    result = process_receipt(tmp_path, current_image_hash)
                    st.session_state['processed_result'] = result

                    # Calculate pie data and Plotly figure immediately after processing
                    categories = ["Food", "Electronics", "Services", "Personal Care", "Household", "Other"]
                    cat_dict = {cat: [] for cat in categories}
                    for item in result["items"]:
                        cat_dict[item["category"]].append(item)
                    pie_data = []
                    for cat in categories:
                        total = sum(item["subtotal"] for item in cat_dict[cat])
                        if total > 0:
                            pie_data.append({"Category": cat, "Total": total})
                    
                    fig = None
                    if pie_data:
                        df = pd.DataFrame(pie_data)
                        fig = px.pie(
                            df, 
                            names="Category", 
                            values="Total", 
                            title="Spending Breakdown",
                            color_discrete_sequence=px.colors.qualitative.Dark24
                        )
                    
                    st.session_state['plotly_fig'] = fig
                    st.session_state['pie_data'] = pie_data
                    st.session_state['current_display_hash'] = current_image_hash # Mark this hash as processed and displayed

                    # --- Save to DB ---
                    session = Session()
                    user = session.query(User).filter_by(email=st.session_state['user_email']).first()
                    if user:
                        # Parse date
                        from dateutil import parser as date_parser
                        try:
                            # Try to parse the date from store info
                            receipt_date = date_parser.parse(result['store_info']['date'])
                            # Ensure the date has no timezone info (convert to system timezone if it does)
                            if receipt_date.tzinfo is not None:
                                receipt_date = receipt_date.astimezone().replace(tzinfo=None)
                        except (ValueError, TypeError, KeyError):
                            # If date parsing fails, use current date
                            receipt_date = datetime.now()
                            st.warning("Could not parse receipt date. Using current date instead.")
                        
                        # Ensure the date is not in the future
                        if receipt_date > datetime.now():
                            receipt_date = datetime.now()
                            st.warning("Receipt date was in the future. Using current date instead.")
                        
                        vendor = result['store_info']['name']
                        total = result['transaction_details']['total']
                        items_json = json.dumps(result['items'])
                        categories_json = json.dumps([item['category'] for item in result['items']])
                        new_receipt = Receipt(
                            user_id=user.id,
                            date=receipt_date,
                            vendor=vendor,
                            total=total,
                            items=items_json,
                            categories=categories_json
                        )
                        session.add(new_receipt)
                        session.commit()
                    session.close()
                    # --- End Save to DB ---

                except Exception as e:
                    st.error(f"Error processing receipt: {str(e)}")
                    st.session_state['processed_result'] = None
                    st.session_state['plotly_fig'] = None
                    st.session_state['pie_data'] = None
                    st.session_state['current_display_hash'] = None
    
    # Now, whether processed or retrieved, display the data if available
    if 'processed_result' in st.session_state and st.session_state['processed_result'] is not None:
        result_to_display = st.session_state['processed_result']
        fig_to_display = st.session_state.get('plotly_fig')
        pie_data_to_display = st.session_state.get('pie_data', [])

        # Apply Plotly theme adjustments to the figure *before* displaying
        if fig_to_display:
            if st.session_state['theme'] == 'dark':
                plotly_paper_bgcolor = '#1e1e1e'
                plotly_plot_bgcolor = '#1e1e1e'
                plotly_title_font_color = '#bb86fc'
                plotly_font_color = '#e0e0e0'
            else:
                plotly_paper_bgcolor = '#f0f2f6'
                plotly_plot_bgcolor = '#f0f2f6'
                plotly_title_font_color = '#6200ee'
                plotly_font_color = '#333333'

            fig_to_display.update_layout(
                showlegend=True,
                legend=dict(orientation="h", yanchor="bottom", y=-0.2, xanchor="center", x=0.5, font=dict(color=plotly_font_color)),
                margin=dict(t=40, b=0, l=0, r=0),
                paper_bgcolor=plotly_paper_bgcolor,
                plot_bgcolor=plotly_plot_bgcolor,
                title_font_color=plotly_title_font_color,
                font_color=plotly_font_color
            )

        # Display store info in a styled card
        st.markdown("### 🏪 Store Information")
        store = result_to_display["store_info"]
        st.markdown(
            f"""
            <div style='background:var(--card-bg); padding:1.2em 1.5em; border-radius:18px; margin-bottom:1.5em; color:var(--text-color);'>
                <b>Name:</b> {store['name']}<br>
                <b>Address:</b> {store['address']}<br>
                <b>Phone:</b> {store['phone']}<br>
                <b>Date:</b> {store['date']}
            </div>
            """,
            unsafe_allow_html=True
        )

        # Transaction Details Card
        txn = result_to_display["transaction_details"]
        change = txn.get("change", 0.0)
        st.markdown(
            f"""
            <div style='background:var(--card-bg); padding:1.2em 1.5em; border-radius:18px; margin-bottom:1.5em; color:var(--text-color);'>
                <b>Total:</b> <span style='color:var(--accent-color-1);font-weight:bold;'>${txn['total']:.2f}</span><br>
                <b>Tax:</b> <span style='color:var(--primary-color);'>${txn['tax']:.2f}</span><br>
                <b>Subtotal:</b> <span style='color:var(--accent-color-1);'>${txn['subtotal']:.2f}</span><br>
                <b>Payment Method:</b> <span style='color:var(--accent-color-2);'>{txn['payment_method']}</span><br>
                <b>Change:</b> <span style='color:var(--accent-color-1);'>${change:.2f}</span>
            </div>
            """,
            unsafe_allow_html=True
        )

        # Display categorized items
        st.markdown("### Categorized Items")
        categories = ["Food", "Electronics", "Services", "Personal Care", "Household", "Other"]
        cat_dict = {cat: [] for cat in categories}
        
        for item in result_to_display["items"]:
            cat_dict[item["category"]].append(item)

        # Category icons
        category_icons = {
            "Food": "🛒",
            "Electronics": "💻",
            "Services": "🛠️",
            "Personal Care": "🧴",
            "Household": "🏠",
            "Other": "📦"
        }
        
        # Filter out empty categories
        non_empty_categories = [cat for cat in categories if len(cat_dict[cat]) > 0]
        cols = st.columns(len(non_empty_categories))

        for idx, cat in enumerate(non_empty_categories):
            with cols[idx]:
                st.markdown(
                    f"""
                    <div class='category-card'>
                        <div style='font-size:1.2em;font-weight:bold;color:var(--primary-color);margin-bottom:0.5em;'>{category_icons[cat]} {cat} ({len(cat_dict[cat])})</div>
                    """,
                    unsafe_allow_html=True
                )
                for item in cat_dict[cat]:
                    st.markdown(
                        f"""
                        <div class='item-card'>
                            <div class='item-title'>{item['name']}</div>
                            <div class='item-desc'>{item.get('description','')}</div>
                            <div class='item-detail'><b>Qty:</b> <span class='item-qty'>{item['quantity']}</span></div>
                            <div class='item-detail'><b>Price:</b> <span class='item-price'>${item['price']:.2f}</span></div>
                            <div class='item-detail'><b>Subtotal:</b> <span class='item-subtotal'>${item['subtotal']:.2f}</span></div>
                        </div>
                        """,
                        unsafe_allow_html=True
                    )
                st.markdown("</div>", unsafe_allow_html=True)

        # Pie chart for spending by category
        st.markdown("### Spending by Category")
        if fig_to_display:
            st.plotly_chart(fig_to_display, use_container_width=True)
        else:
            st.info("No spending data available for visualization.")

        # Export Buttons
        st.markdown("### Export Data")
        col1, col2, col3 = st.columns(3)

        store = result_to_display["store_info"]
        txn = result_to_display["transaction_details"]
        items = result_to_display["items"]

        with col1:
            csv_data = export_to_csv(store, txn, items)
            st.download_button(
                label="Export as CSV",
                data=csv_data,
                file_name="receipt_data.csv",
                mime="text/csv",
                key="csv_download"
            )
        with col2:
            excel_data = export_to_excel(store, txn, items, pie_data_to_display)
            st.download_button(
                label="Export as Excel",
                data=excel_data,
                file_name="receipt_data.xlsx",
                mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                key="excel_download"
            )
        with col3:
            if fig_to_display:
                pdf_data = export_to_pdf(store, txn, items, fig_to_display)
            else:
                pdf_data = export_to_pdf(store, txn, items, None)
            st.download_button(
                label="Export as PDF",
                data=pdf_data,
                file_name="receipt_report.pdf",
                mime="application/pdf",
                key="pdf_download"
            )
    
    # Clean up temp file
    if 'tmp_path' in locals() and tmp_path and os.path.exists(tmp_path):
        os.remove(tmp_path)
    # Only show the info message if no receipt has ever been uploaded in this session
    elif (
        ('processed_result' not in st.session_state or st.session_state['processed_result'] is None)
        and (st.session_state.get('uploaded_image_file') is None)
    ):
        st.info("Upload a receipt image to get started.")

elif page == "Analytics":
    st.title("📊 Advanced Analytics")
    st.markdown("<div style='margin-bottom:2em'></div>", unsafe_allow_html=True)
    session = Session()
    user = session.query(User).filter_by(email=st.session_state['user_email']).first()
    if user:
        receipts = session.query(Receipt).filter_by(user_id=user.id).order_by(Receipt.date).all()
        if not receipts:
            st.info("No receipts found. Upload receipts to see analytics.")
        else:
            # Prepare DataFrame
            data = []
            for r in receipts:
                items = json.loads(r.items)
                for item in items:
                    data.append({
                        'date': r.date,
                        'vendor': r.vendor,
                        'category': item.get('category', 'Other'),
                        'amount': item.get('subtotal', 0.0)
                    })
            df = pd.DataFrame(data)
            if df.empty:
                st.info("No item data found in receipts.")
            else:
                df['date'] = pd.to_datetime(df['date'])
                df['month'] = df['date'].dt.to_period('M').astype(str)
                df['week'] = df['date'].dt.to_period('W').astype(str)

                # --- Monthly Spending Trend ---
                st.markdown("#### 📅 Monthly Spending Trend")
                monthly = df.groupby('month')['amount'].sum().reset_index()
                fig_month = px.bar(monthly, x='month', y='amount', labels={'amount': 'Total Spent ($)'}, color='amount', color_continuous_scale='Blues')
                fig_month.update_layout(height=320, margin=dict(t=30, b=0, l=0, r=0), plot_bgcolor='rgba(0,0,0,0)', paper_bgcolor='rgba(0,0,0,0)')
                st.plotly_chart(fig_month, use_container_width=True)

                # --- Weekly Spending Trend ---
                st.markdown("#### 📆 Weekly Spending Trend")
                weekly = df.groupby('week')['amount'].sum().reset_index()
                fig_week = px.line(weekly, x='week', y='amount', markers=True, labels={'amount': 'Total Spent ($)'})
                fig_week.update_layout(height=320, margin=dict(t=30, b=0, l=0, r=0), plot_bgcolor='rgba(0,0,0,0)', paper_bgcolor='rgba(0,0,0,0)')
                st.plotly_chart(fig_week, use_container_width=True)

                # --- Top Categories ---
                st.markdown("#### 🏷️ Top Spending Categories")
                cat_sum = df.groupby('category')['amount'].sum().reset_index().sort_values('amount', ascending=False)
                fig_cat = px.bar(cat_sum, x='category', y='amount', color='amount', color_continuous_scale='Teal', labels={'amount': 'Total Spent ($)'})
                fig_cat.update_layout(height=320, margin=dict(t=30, b=0, l=0, r=0), plot_bgcolor='rgba(0,0,0,0)', paper_bgcolor='rgba(0,0,0,0)')
                st.plotly_chart(fig_cat, use_container_width=True)

                # --- Top Vendors ---
                st.markdown("#### 🏪 Top Vendors")
                vendor_sum = df.groupby('vendor')['amount'].sum().reset_index().sort_values('amount', ascending=False).head(10)
                fig_vendor = px.bar(vendor_sum, x='vendor', y='amount', color='amount', color_continuous_scale='Oranges', labels={'amount': 'Total Spent ($)'})
                fig_vendor.update_layout(height=320, margin=dict(t=30, b=0, l=0, r=0), plot_bgcolor='rgba(0,0,0,0)', paper_bgcolor='rgba(0,0,0,0)')
                st.plotly_chart(fig_vendor, use_container_width=True)
    else:
        st.error("User not found.")
    session.close()

elif page == "Budgets":
    st.title("💰 Budgets & Alerts")
    st.markdown("<div style='margin-bottom:2em'></div>", unsafe_allow_html=True)
    session = Session()
    user = session.query(User).filter_by(email=st.session_state['user_email']).first()
    if not user:
        st.error("User not found.")
        session.close()
    else:
        # Get all unique months from receipts
        all_receipts = session.query(Receipt).filter_by(user_id=user.id).all()
        unique_months = sorted(set(r.date.strftime('%Y-%m') for r in all_receipts))
        
        # Add current month if not in list
        current_month = datetime.now().strftime('%Y-%m')
        if current_month not in unique_months:
            unique_months.append(current_month)
        unique_months.sort(reverse=True)  # Most recent first

        # Default to most recent month that has receipts, fall back to current month
        months_with_data = sorted(set(r.date.strftime('%Y-%m') for r in all_receipts), reverse=True)
        default_month = months_with_data[0] if months_with_data else current_month

        # Month selector
        selected_month = st.selectbox(
            "Select Month",
            unique_months,
            index=unique_months.index(default_month) if default_month in unique_months else 0
        )
        
        # Determine if selected month is in the past
        selected_year, selected_month_num = map(int, selected_month.split('-'))
        is_past_month = datetime(selected_year, selected_month_num, 1) < datetime.now().replace(day=1, hour=0, minute=0, second=0, microsecond=0)
        
        if is_past_month:
            st.info("📊 Viewing historical spending data. Budgets cannot be set for past months.")
        else:
            st.success("💰 Set your budgets for this month below.")
        
        st.markdown("<div style='margin-bottom:2em'></div>", unsafe_allow_html=True)
        
        # --- Budget Form ---
        if not is_past_month:
            st.markdown("#### Set Monthly Budgets per Category")
            categories = ["Food", "Electronics", "Services", "Personal Care", "Household", "Other"]
            budget_dict = {b.category: b for b in session.query(Budget).filter_by(user_id=user.id, month=selected_month).all()}
            with st.form("budget_form"):
                cols = st.columns(len(categories))
                new_budgets = {}
                for idx, cat in enumerate(categories):
                    with cols[idx]:
                        val = budget_dict[cat].amount if cat in budget_dict else 0.0
                        new_budgets[cat] = st.number_input(f"{cat}", min_value=0.0, value=float(val), step=10.0, format="%.2f")
                submitted = st.form_submit_button("Save Budgets")
                if submitted:
                    for cat, amt in new_budgets.items():
                        b = budget_dict.get(cat)
                        if b:
                            b.amount = amt
                        else:
                            b = Budget(user_id=user.id, category=cat, month=selected_month, amount=amt)
                            session.add(b)
                    session.commit()
                    st.success("Budgets saved!")
                    st.rerun()
            st.markdown("<div style='margin-bottom:2em'></div>", unsafe_allow_html=True)
        
        # --- Spending vs. Budget ---
        if is_past_month:
            st.markdown("#### Monthly Spending Breakdown")
        else:
            st.markdown("#### This Month's Spending vs. Budget")
        
        # Parse selected month
        year, month = map(int, selected_month.split('-'))
        first_day = datetime(year, month, 1)
        if month == 12:
            next_month = first_day.replace(year=year + 1, month=1)
        else:
            next_month = first_day.replace(month=month + 1)
            
        # Get filtered receipts and calculate spending
        receipts = session.query(Receipt).filter_by(user_id=user.id).filter(
            Receipt.date >= first_day,
            Receipt.date < next_month
        ).all()
        
        categories = ["Food", "Electronics", "Services", "Personal Care", "Household", "Other"]
        spend_data = {cat: 0.0 for cat in categories}
        
        for r in receipts:
            items = json.loads(r.items)
            for item in items:
                cat = item.get('category', 'Other')
                amount = item.get('subtotal', 0.0)
                spend_data[cat] += amount
        
        # Display spending data
        for cat in categories:
            spent = spend_data[cat]
            if is_past_month:
                # For past months, just show the spending amount
                st.markdown(
                    f"""
                    <div style='background:var(--card-bg);padding:1em 1.5em;border-radius:12px;margin-bottom:1.2em;box-shadow:0 2px 8px rgba(0,0,0,0.10);'>
                        <b>{cat}</b>  &nbsp;  ${spent:.2f}
                    </div>
                    """,
                    unsafe_allow_html=True
                )
            else:
                # For current/future months, show budget comparison
                budget = new_budgets.get(cat, 0.0)
                percent = spent / budget * 100 if budget > 0 else 0
                bar_color = '#03dac6' if percent < 80 else ('#ffb300' if percent < 100 else '#ff1744')
                st.markdown(
                    f"""
                    <div style='background:var(--card-bg);padding:1em 1.5em;border-radius:12px;margin-bottom:1.2em;box-shadow:0 2px 8px rgba(0,0,0,0.10);'>
                        <b>{cat}</b>  &nbsp;  ${spent:.2f} / ${budget:.2f}
                    </div>
                    """,
                    unsafe_allow_html=True
                )
                st.progress(min(percent/100, 1.0), text=f"{percent:.0f}% of budget")
                if budget > 0 and percent >= 90 and percent < 100:
                    st.warning(f"You're approaching your {cat} budget!")
                elif budget > 0 and percent >= 100:
                    st.error(f"You have exceeded your {cat} budget!")
        session.close()

# Add user info and logout button
st.sidebar.markdown(
    f"""
    <div style='
        padding:1.2em 1em;
        background: var(--card-bg);
        border-radius: 14px;
        margin-bottom: 1.5em;
        box-shadow: 0 2px 8px rgba(0,0,0,0.10);
        width: fit-content;
        min-width: 180px;
        max-width: 100%;
        word-break: break-all;
        display: inline-block;
    '>
        <div style='color:var(--text-color); font-size:0.9em; margin-bottom:0.7em;'>
            Logged in as: <b>{st.session_state['user_email']}</b>
        </div>
    </div>
    """,
    unsafe_allow_html=True
)

if st.sidebar.button("Logout", use_container_width=True):
    token = st.session_state.get('session_token')
    if token:
        delete_session(token)
    st.query_params.clear()
    st.session_state.clear()
    st.session_state['authenticated'] = False
    st.session_state['show_register'] = False
    st.rerun()

