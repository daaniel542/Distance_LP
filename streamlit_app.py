
# streamlit_app.py
import os
from dotenv import load_dotenv
load_dotenv()

import streamlit as st
import pandas as pd
from tempfile import NamedTemporaryFile
import pathlib
from lane_distance import process_file

st.set_page_config(
    page_title="Lane Distance Calculator",
    page_icon="🛫",
    layout="wide"
)

# Sidebar: Instructions
README = pathlib.Path(__file__).parent / "README.MD"
st.sidebar.header("📖 Instructions")
if README.exists():
    st.sidebar.markdown(README.read_text(encoding="utf-8"))
else:
    st.sidebar.warning("README.MD not found.")

# Sidebar: Sample Data
st.sidebar.header("📑 Sample Data")
for sf in pathlib.Path(__file__).parent.glob("sample_data.*"):
    mime = (
        "text/csv" if sf.suffix.lower() == ".csv" else
        "application/vnd.ms-excel" if sf.suffix.lower() == ".xls" else
        "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
    )
    st.sidebar.download_button(
        label=f"Download {sf.name}",
        data=sf.read_bytes(),
        file_name=sf.name,
        mime=mime
    )

# Main UI
st.title("🛫 Lane Distance Calculator")
st.markdown(
    """
    Upload a CSV or Excel file with **Origin** and **Destination** columns,
    then click **Calculate Distances** to get lat/lon + distance.
    """
)

uploaded = st.file_uploader("📂 Choose a file", type=["csv", "xls", "xlsx"])
if uploaded:
    suffix = pathlib.Path(uploaded.name).suffix.lower()
    df = pd.read_excel(uploaded) if suffix in (".xls", ".xlsx") else pd.read_csv(uploaded)
    st.subheader("Data Preview")
    st.dataframe(df.head())

    if st.button("🚀 Calculate Distances"):
        with st.spinner("Processing…"):
            with NamedTemporaryFile(delete=False, suffix=suffix) as tmp:
                tmp.write(uploaded.getvalue())
                tmp_path = pathlib.Path(tmp.name)

            out_path = process_file(tmp_path)
            res = pd.read_excel(out_path) if out_path.suffix in (".xls", ".xlsx") else pd.read_csv(out_path)

            st.success("✅ Done!")
            st.dataframe(res)

            st.download_button(
                "Download CSV",
                data=res.to_csv(index=False).encode("utf-8"),
                file_name="results.csv",
                mime="text/csv"
            )
            excel_tmp = NamedTemporaryFile(delete=False, suffix=".xlsx")
            res.to_excel(excel_tmp.name, index=False)
            st.download_button(
                "Download Excel",
                data=pathlib.Path(excel_tmp.name).read_bytes(),
                file_name="results.xlsx",
                mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
            )

# Sidebar: Info
st.sidebar.header("ℹ️ Info")
st.sidebar.markdown(
    """
    **Geocoding Service**: Mapbox API  
    **Rate-limit**: 1 req/sec, 2 retries  
    """
)