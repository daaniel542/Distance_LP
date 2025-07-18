# streamlit_app.py
########################################
# Streamlit Web Interface for Lane Distance Calculator
########################################

import streamlit as st
import pandas as pd
import io
from tempfile import NamedTemporaryFile
import pathlib
import os
from lane_distance import process_file

# Page configuration
st.set_page_config(
    page_title="Lane Distance Calculator",
    page_icon="🛫",
    layout="wide"
)

st.title("🛫 Lane Distance Calculator")
st.markdown("""
Upload a CSV or Excel file with **origin** and **destination** columns.
The app will compute crow-flight distances, pick the farthest match when
names collide, and highlight any ambiguous city lookups.
""")

uploaded_file = st.file_uploader(
    "Upload your CSV or Excel file", type=["csv", "xls", "xlsx"]
)

# only show the calculate button once a file is present
if uploaded_file:
    st.success(f"File uploaded: {uploaded_file.name} ({uploaded_file.size:,} bytes)")
    
    # preview first 5 rows
    try:
        if uploaded_file.name.lower().endswith((".xls", ".xlsx")):
            df_preview = pd.read_excel(uploaded_file, nrows=5)
        else:
            df_preview = pd.read_csv(uploaded_file, nrows=5)
        st.subheader("📊 Data Preview (First 5 rows)")
        st.dataframe(df_preview)
    except Exception as e:
        st.error(f"Failed to parse file: {e}")
    
    # show Calculate button
    if st.button("🚀 Calculate Distances"):
        # write upload to a temp file
        suffix = pathlib.Path(uploaded_file.name).suffix
        with NamedTemporaryFile(delete=False, suffix=suffix) as tmp:
            tmp.write(uploaded_file.getbuffer())
            tmp_path = pathlib.Path(tmp.name)

        # process it
        result_df = process_file(
            tmp_path,
            tmp_path.parent / f"processed_{uploaded_file.name}"
        )

        st.success("✅ Computed lane distances")
        st.dataframe(result_df)

        # --- CSV download
        csv_bytes = result_df.to_csv(index=False).encode("utf-8")
        st.download_button(
            label="📥 Download Results as CSV",
            data=csv_bytes,
            file_name=f"processed_{uploaded_file.name}.csv",
            mime="text/csv",
        )

        # --- Excel download
        excel_buffer = io.BytesIO()
        with pd.ExcelWriter(excel_buffer, engine="openpyxl") as writer:
            result_df.to_excel(writer, index=False, sheet_name="Distances")
            writer.save()
        excel_buffer.seek(0)
        st.download_button(
            label="📥 Download Results as Excel",
            data=excel_buffer,
            file_name=f"processed_{uploaded_file.name}.xlsx",
            mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        )

# Sidebar: sample file for reference
st.sidebar.header("📄 Sample File")
sample_df = pd.DataFrame({
    "origin":      ["Chicago, US", "Los Angeles, US"],
    "destination": ["New York, US", "Miami, US"],
})
st.sidebar.write("Download this to see the required format:")
sample_csv = sample_df.to_csv(index=False)
st.sidebar.download_button(
    label="Download Sample CSV",
    data=sample_csv,
    file_name="sample_lane_data.csv",
    mime="text/csv",
)

# Sidebar: network info
st.sidebar.header("ℹ️ Network Info")
st.sidebar.markdown("""
**Geocoding Service**: Mapbox Geocoding API  
**Rate Limits**:  
- 1 second between requests  
- 2 retry attempts per location  

**Requirements**:  
- Internet connection  
- `MAPBOX_TOKEN` environment variable set  
""")
