import os
from dotenv import load_dotenv    # ← load .env at startup
load_dotenv()

import streamlit as st
import pandas as pd
from tempfile import NamedTemporaryFile
import pathlib
from lane_distance import process_file

# ─── Page config ───────────────────────────────────────────────────────────────
st.set_page_config(
    page_title="Lane Distance Calculator",
    page_icon="🛫",
    layout="wide"
)

# ─── Sidebar: Instructions ──────────────────────────────────────────────────────
README_PATH = pathlib.Path(__file__).parent / "README.MD"
if README_PATH.exists():
    with open(README_PATH, "r", encoding="utf-8") as f:
        readme_text = f.read()
    st.sidebar.header("📖 Instructions")
    st.sidebar.markdown(readme_text)
else:
    st.sidebar.warning("README.MD not found in project root. Please ensure it is present.")

# ─── Sidebar: Sample Data ──────────────────────────────────────────────────────
SAMPLE_DIR = pathlib.Path(__file__).parent
sample_files = list(SAMPLE_DIR.glob("sample_data.*"))
if sample_files:
    st.sidebar.header("📑 Sample Data")
    for sf in sample_files:
        with open(sf, "rb") as f:
            data = f.read()
        mime = (
            "text/csv" if sf.suffix.lower() == ".csv"
            else "application/vnd.ms-excel" if sf.suffix.lower() == ".xls"
            else "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
        )
        st.sidebar.download_button(
            f"Download {sf.name}",
            data=data,
            file_name=sf.name,
            mime=mime,
        )

# ─── Main App UI ───────────────────────────────────────────────────────────────
st.title("🛫 Lane Distance Calculator")
st.markdown(
    """
    Upload a CSV or Excel file with columns **Origin** and **Destination**,  
    then click **Calculate Distances**.
    """
)

uploaded_file = st.file_uploader(
    "📂 Choose a file", type=["csv", "xls", "xlsx"]
)
if uploaded_file is not None:
    suffix = pathlib.Path(uploaded_file.name).suffix.lower()
    df = (
        pd.read_excel(uploaded_file)
        if suffix in (".xls", ".xlsx")
        else pd.read_csv(uploaded_file)
    )
    st.subheader("📊 Data Preview")
    st.dataframe(df.head())

    if st.button("🚀 Calculate Distances"):
        with st.spinner("Processing… this may take a few minutes."):
            # write to temp file for lane_distance.process_file
            with NamedTemporaryFile(delete=False, suffix=suffix) as tmp:
                tmp.write(uploaded_file.getvalue())
                tmp_path = pathlib.Path(tmp.name)

            out_path = tmp_path.with_name(f"{tmp_path.stem}_processed{tmp_path.suffix}")
            process_file(tmp_path, out_path)

            result_df = (
                pd.read_excel(out_path)
                if out_path.suffix in (".xls", ".xlsx")
                else pd.read_csv(out_path)
            )
            st.success("✅ Done calculating distances!")
            st.dataframe(result_df.head())

            # CSV download
            csv_bytes = result_df.to_csv(index=False).encode("utf-8")
            st.download_button(
                "📥 Download CSV",
                data=csv_bytes,
                file_name=out_path.with_suffix(".csv").name,
                mime="text/csv",
            )

            # Excel download
            excel_tmp = NamedTemporaryFile(delete=False, suffix=".xlsx")
            result_df.to_excel(excel_tmp.name, index=False)
            with open(excel_tmp.name, "rb") as fp:
                st.download_button(
                    "📥 Download Excel",
                    data=fp.read(),
                    file_name=out_path.with_suffix(".xlsx").name,
                    mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                )

# ─── Sidebar: Info ───────────────────────────────────────────────────────────
st.sidebar.header("ℹ️ Network & Rate-Limit Info")
st.sidebar.markdown(
    """
    **Geocoding Service**: Mapbox API  
    **Rate Limits**: 1 request/sec, 2 retries  
    """
)
