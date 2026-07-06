"""
Document Processing Agent — Streamlit UI

Premium dark-themed interface for uploading documents, processing them
through the ADK multi-agent pipeline, and downloading summaries.
"""

import streamlit as st
import streamlit.components.v1 as components
import os
import shutil
from main import run_pipeline
import asyncio
import base64

from dotenv import load_dotenv
load_dotenv()

# ---------------------------------------------------------------------------
# Page Config
# ---------------------------------------------------------------------------
st.set_page_config(
    page_title="Document Processing Agent",
    page_icon="📄",
    layout="wide",
    initial_sidebar_state="collapsed",
)

# ---------------------------------------------------------------------------
# Custom CSS 
# ---------------------------------------------------------------------------
st.markdown("""
<style>
    @import url('https://fonts.googleapis.com/css2?family=Inter:wght@300;400;500;600;700;800&display=swap');

    /* ---- Global ---- */
    .stApp {
        background: linear-gradient(135deg, #0f0c29 0%, #1a1a3e 30%, #24243e 60%, #0f0c29 100%);
        font-family: 'Inter', sans-serif;
    }

    /* ---- Sidebar hide ---- */
    [data-testid="stSidebar"] { display: none; }

    /* ---- Header ---- */
    .hero-header {
        text-align: center;
        padding: 2.5rem 1rem 1.5rem;
        animation: fadeInDown 0.8s ease-out;
    }
    .hero-header h1 {
        font-size: 2.8rem;
        font-weight: 800;
        background: linear-gradient(135deg, #667eea 0%, #764ba2 50%, #f093fb 100%);
        -webkit-background-clip: text;
        -webkit-text-fill-color: transparent;
        background-clip: text;
        margin-bottom: 0.3rem;
    }
    .hero-header p {
        color: #8b8fa3;
        font-size: 1.05rem;
        font-weight: 300;
    }

    /* ---- Glass Card ---- */
    .glass-card {
        background: rgba(255, 255, 255, 0.04);
        backdrop-filter: blur(20px);
        -webkit-backdrop-filter: blur(20px);
        border: 1px solid rgba(255, 255, 255, 0.08);
        border-radius: 16px;
        padding: 1.8rem;
        margin-bottom: 1.5rem;
        animation: fadeInUp 0.6s ease-out;
        transition: border-color 0.3s ease, box-shadow 0.3s ease;
    }
    .glass-card:hover {
        border-color: rgba(102, 126, 234, 0.3);
        box-shadow: 0 8px 32px rgba(102, 126, 234, 0.1);
    }
    .glass-card h3 {
        color: #e0e0ff;
        font-weight: 600;
        font-size: 1.2rem;
        margin-bottom: 1rem;
        display: flex;
        align-items: center;
        gap: 0.5rem;
    }

    /* ---- Upload Area ---- */
    [data-testid="stFileUploader"] {
        background: rgba(102, 126, 234, 0.06);
        border: 2px dashed rgba(102, 126, 234, 0.3);
        border-radius: 12px;
        padding: 1rem;
        transition: all 0.3s ease;
    }
    [data-testid="stFileUploader"]:hover {
        border-color: rgba(102, 126, 234, 0.6);
        background: rgba(102, 126, 234, 0.1);
    }
    [data-testid="stFileUploader"] label {
        color: #c0c4e0 !important;
        font-weight: 500;
    }

    /* ---- Buttons ---- */
    .stButton > button {
        background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
        color: white;
        border: none;
        border-radius: 10px;
        padding: 0.7rem 2rem;
        font-weight: 600;
        font-size: 1rem;
        font-family: 'Inter', sans-serif;
        transition: all 0.3s ease;
        box-shadow: 0 4px 15px rgba(102, 126, 234, 0.3);
    }
    .stButton > button:hover {
        transform: translateY(-2px);
        box-shadow: 0 6px 25px rgba(102, 126, 234, 0.45);
    }
    .stButton > button:active {
        transform: translateY(0);
    }
    .stDownloadButton > button {
        background: linear-gradient(135deg, #11998e 0%, #38ef7d 100%);
        color: #0f0c29;
        border: none;
        border-radius: 10px;
        padding: 0.5rem 1.5rem;
        font-weight: 600;
        font-family: 'Inter', sans-serif;
        transition: all 0.3s ease;
        box-shadow: 0 4px 15px rgba(56, 239, 125, 0.2);
    }
    .stDownloadButton > button:hover {
        transform: translateY(-2px);
        box-shadow: 0 6px 25px rgba(56, 239, 125, 0.35);
    }

    /* ---- Status / Progress ---- */
    .status-badge {
        display: inline-flex;
        align-items: center;
        gap: 0.4rem;
        padding: 0.35rem 0.85rem;
        border-radius: 20px;
        font-size: 0.8rem;
        font-weight: 600;
    }
    .status-idle {
        background: rgba(139, 143, 163, 0.15);
        color: #8b8fa3;
    }
    .status-processing {
        background: rgba(102, 126, 234, 0.15);
        color: #667eea;
        animation: pulse 1.5s infinite;
    }
    .status-done {
        background: rgba(56, 239, 125, 0.15);
        color: #38ef7d;
    }

    /* ---- File Chip ---- */
    .file-chip {
        display: inline-flex;
        align-items: center;
        gap: 0.4rem;
        background: rgba(102, 126, 234, 0.1);
        border: 1px solid rgba(102, 126, 234, 0.2);
        border-radius: 8px;
        padding: 0.4rem 0.8rem;
        margin: 0.25rem;
        color: #c0c4e0;
        font-size: 0.85rem;
        transition: all 0.2s;
    }
    .file-chip:hover {
        background: rgba(102, 126, 234, 0.2);
    }

    /* ---- Summary Card ---- */
    .summary-card {
        background: rgba(255, 255, 255, 0.03);
        border: 1px solid rgba(255, 255, 255, 0.06);
        border-radius: 12px;
        padding: 1.2rem;
        margin: 0.6rem 0;
        transition: all 0.3s ease;
    }
    .summary-card:hover {
        border-color: rgba(56, 239, 125, 0.3);
        background: rgba(255, 255, 255, 0.05);
    }

    /* ---- Stat Box ---- */
    .stat-box {
        text-align: center;
        padding: 1rem;
        background: rgba(255, 255, 255, 0.03);
        border-radius: 12px;
        border: 1px solid rgba(255, 255, 255, 0.06);
    }
    .stat-number {
        font-size: 2rem;
        font-weight: 700;
        background: linear-gradient(135deg, #667eea, #764ba2);
        -webkit-background-clip: text;
        -webkit-text-fill-color: transparent;
    }
    .stat-label {
        color: #8b8fa3;
        font-size: 0.8rem;
        font-weight: 500;
        text-transform: uppercase;
        letter-spacing: 1px;
        margin-top: 0.3rem;
    }

    /* ---- Animations ---- */
    @keyframes fadeInDown {
        from { opacity: 0; transform: translateY(-20px); }
        to   { opacity: 1; transform: translateY(0); }
    }
    @keyframes fadeInUp {
        from { opacity: 0; transform: translateY(20px); }
        to   { opacity: 1; transform: translateY(0); }
    }
    @keyframes pulse {
        0%, 100% { opacity: 1; }
        50%      { opacity: 0.6; }
    }

    /* ---- Expander styling ---- */
    .streamlit-expanderHeader {
        background: rgba(255, 255, 255, 0.03) !important;
        border-radius: 8px !important;
        color: #c0c4e0 !important;
    }

    /* ---- General text ---- */
    .stMarkdown p, .stMarkdown li {
        color: #c0c4e0;
    }
    .stMarkdown h1, .stMarkdown h2, .stMarkdown h3 {
        color: #e0e0ff;
    }

    /* ---- Progress bar ---- */
    .stProgress > div > div > div > div {
        background: linear-gradient(90deg, #667eea, #764ba2, #f093fb);
    }

    /* ---- Divider ---- */
    hr {
        border: none;
        border-top: 1px solid rgba(255, 255, 255, 0.06);
        margin: 1.5rem 0;
    }
</style>
""", unsafe_allow_html=True)


# ---------------------------------------------------------------------------
# Helper: File type icon
# ---------------------------------------------------------------------------
FILE_ICONS = {
    ".pdf": "📕",
    ".docx": "📘",
    ".csv": "📊",
    ".txt": "📝",
}

def get_file_icon(filename: str) -> str:
    ext = os.path.splitext(filename)[1].lower()
    return FILE_ICONS.get(ext, "📄")


# ---------------------------------------------------------------------------
# Directory Setup
# ---------------------------------------------------------------------------
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
UPLOADS_DIR = os.path.join(BASE_DIR, "uploads")
os.makedirs(UPLOADS_DIR, exist_ok=True)


# ---------------------------------------------------------------------------
# UI Layout
# ---------------------------------------------------------------------------

# Hero Header
st.markdown("""
<div class="hero-header">
    <h1>📄 Document Processing Agent</h1>
    <p>Multi-agent AI pipeline powered by Google ADK — Upload, Extract, Structure</p>
</div>
""", unsafe_allow_html=True)

st.markdown("<hr>", unsafe_allow_html=True)

# Two-column layout
left_col, right_col = st.columns([1, 1], gap="large")

# ---- LEFT: Upload & Process ----
with left_col:
    st.markdown("""
    <div class="glass-card">
        <h3>📤 Upload Documents</h3>
    </div>
    """, unsafe_allow_html=True)

    uploaded_files = st.file_uploader(
        "Drag and drop files here",
        type=["csv", "pdf", "docx", "txt"],
        accept_multiple_files=True,
        help="Supported: PDF, DOCX, CSV, TXT",
    )

    if uploaded_files:
        st.markdown("**Uploaded files:**")
        chips_html = ""
        for uf in uploaded_files:
            icon = get_file_icon(uf.name)
            size_kb = len(uf.getvalue()) / 1024
            chips_html += f'<span class="file-chip">{icon} {uf.name} ({size_kb:.1f} KB)</span>'
        st.markdown(f'<div>{chips_html}</div>', unsafe_allow_html=True)
        st.markdown("")

        # Process button
        if st.button("Process Documents", use_container_width=True, type="primary"):

            # Save uploaded files to disk
            file_paths = []
            if os.path.exists(UPLOADS_DIR):
                shutil.rmtree(UPLOADS_DIR)
            os.makedirs(UPLOADS_DIR, exist_ok=True)

            for uf in uploaded_files:
                file_path = os.path.join(UPLOADS_DIR, uf.name)
                with open(file_path, "wb") as f:
                    f.write(uf.getvalue())
                file_paths.append(file_path)

            with st.spinner("Filtering and processing documents..."):
                try:
                    # Pass the upload directory to your core pipeline execution
                    final_json_string = asyncio.run(
                        run_pipeline(UPLOADS_DIR)  #############
                    )
                    st.session_state.final_result = final_json_string
                    st.success("Processing complete!")
                except Exception as e:
                    st.error(f"An error occurred: {e}")

# ---- RIGHT: Results & Downloads ----
with right_col:
    st.markdown("""
    <div class="glass-card">
        <h3>📥 Result PDF</h3>
    </div>
    """, unsafe_allow_html=True)

    OUTPUT_PDF_PATH = os.path.join(BASE_DIR, "output", "result_KYC.pdf")

    if os.path.exists(OUTPUT_PDF_PATH):
        with open(OUTPUT_PDF_PATH, "rb") as f:
            pdf_bytes = f.read()

        # Download button
        st.download_button(
            label="⬇️ Download KYC Report",
            data=pdf_bytes,
            file_name="result_KYC.pdf",
            mime="application/pdf",
            use_container_width=True,
        )

        # Inline preview via base64-embedded iframe using components.html
        # (st.markdown sanitises data: URIs, so the iframe never rendered)
        base64_pdf = base64.b64encode(pdf_bytes).decode("utf-8")
        pdf_display = f"""
        <iframe
            src="data:application/pdf;base64,{base64_pdf}"
            width="100%"
            height="600"
            style="border: none; border-radius: 8px;">
        </iframe>
        """
        components.html(pdf_display, height=620, scrolling=False)
    else:
        st.info("Upload and process documents to see the KYC report here.")