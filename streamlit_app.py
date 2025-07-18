import os
from dotenv import load_dotenv    # ← load .env at startup
load_dotenv()

import streamlit as st
import pandas as pd
from tempfile import NamedTemporaryFile
import pathlib
from lane_distance import process_file

st.set_page_config(page_title="Lane Distance Calculator", page_icon="🛫", layout="wide")

st.title("🛫 Lane Distance Calculator")
st.markdown("""
Upload a CSV or Excel file with columns **Origin** and **Destination**, 
then click **Calculate Distances**.
""")

uploaded = st.file_uploader("📂 Choose file", type=["csv", "xls", "xlsx"])
if uploaded:
    suffix = pathlib.Path(uploaded.name).suffix.lower()
    df = pd.read_excel(uploaded) if suffix in (".xls", ".xlsx") else pd.read_csv(uploaded)

    st.subheader("Data Preview")
    st.dataframe(df.head())

    if st.button("🚀 Calculate Distances"):
        with st.spinner("Processing…"):
            # dump to temp file so process_file can read it
            with NamedTemporaryFile(delete=False, suffix=suffix) as tmp:
                tmp.write(uploaded.getvalue())
                tmp_path = pathlib.Path(tmp.name)

            out_path = process_file(tmp_path)

            # load back
            res = (pd.read_excel(out_path) 
                   if out_path.suffix in (".xls", ".xlsx") 
                   else pd.read_csv(out_path))

            st.success("✅ Done!")
            st.dataframe(res.head())

            # CSV download
            st.download_button(
                "Download CSV",
                data=res.to_csv(index=False).encode("utf-8"),
                file_name=out_path.with_suffix(".csv").name,
                mime="text/csv"
            )
            # Excel download
            excel_tmp = NamedTemporaryFile(delete=False, suffix=".xlsx")
            res.to_excel(excel_tmp.name, index=False)
            with open(excel_tmp.name, "rb") as fp:
                st.download_button(
                    "Download Excel",
                    data=fp.read(),
                    file_name=out_path.with_suffix(".xlsx").name,
                    mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
                )

st.sidebar.header("ℹ️ Info")
st.sidebar.markdown("""
**Geocoding Service**: Mapbox API  
**Rate limit**: 1 req/sec, 2 retries  
""")
