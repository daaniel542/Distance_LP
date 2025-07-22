# streamlit_app.py

import os
import time
import base64
import io
import pathlib

import streamlit as st
import pandas as pd

from lane_distance import resolve_place, great_circle
from dotenv import load_dotenv

load_dotenv()

st.set_page_config(page_title="Lane Distance Calculator", page_icon="🛫", layout="wide")

README = pathlib.Path(__file__).parent / "README.MD"
if README.exists():
    st.sidebar.markdown(README.read_text())

st.title("🛫 Lane Distance Calculator")
uploaded = st.file_uploader("Upload CSV or Excel", type=["csv", "xls", "xlsx"])

if uploaded:
    # Read input
    if uploaded.name.lower().endswith((".xls", ".xlsx")):
        df_input = pd.read_excel(uploaded)
    else:
        df_input = pd.read_csv(uploaded)

    cols_lower = [c.lower() for c in df_input.columns]
    origin_code_col = next((c for i, c in zip(cols_lower, df_input.columns) if 'origin' in i and 'locode' in i), None)
    dest_code_col = next((c for i, c in zip(cols_lower, df_input.columns) if ('dest' in i or 'destination' in i) and 'locode' in i), None)

    if st.button("Calculate"):
        total = len(df_input)
        status = st.empty()
        progress = st.progress(0)
        results = []
        start_time = time.time()

        for idx, row in df_input.iterrows():
            elapsed = time.time() - start_time
            status.text(f"Elapsed: {elapsed:.1f}s | Rows left: {total - idx - 1}")
            progress.progress((idx + 1) / total)

            # Extract fields
            name_o = row.get('Origin') or row.get('origin')
            code_o = row.get(origin_code_col) if origin_code_col else None
            name_d = row.get('Destination') or row.get('destination')
            code_d = row.get(dest_code_col) if dest_code_col else None

            # Resolve origin
            try:
                lat_o, lon_o, amb_o, used_o = resolve_place(name_o, code_o)
                err_o = None
            except Exception as e:
                lat_o = lon_o = None
                amb_o = True
                used_o = False
                err_o = str(e)

            # Resolve destination
            try:
                lat_d, lon_d, amb_d, used_d = resolve_place(name_d, code_d)
                err_d = None
            except Exception as e:
                lat_d = lon_d = None
                amb_d = True
                used_d = False
                err_d = str(e)

            # Determine if both used UNLOCODE
            used_both = bool(used_o and used_d)
            if used_both:
                amb_o = amb_d = ""

            # Calculate distance
            error_msg = err_o or err_d or ""
            distance = None
            if not error_msg and None not in (lat_o, lon_o, lat_d, lon_d):
                distance = great_circle(lat_o, lon_o, lat_d, lon_d)

            # Collect results
            results.append({
                'Origin': name_o,
                'Destination': name_d,
                'Origin LOCODE': code_o,
                'Destination LOCODE': code_d,
                'Origin latitude': lat_o,
                'Origin longitude': lon_o,
                'Destination latitude': lat_d,
                'Destination longitude': lon_d,
                'Distance_miles': distance,
                'Used UNLOCODEs': used_both,
                'Ambiguous Origin': amb_o,
                'Ambiguous Destination': amb_d,
                'Error_msg': error_msg
            })

        # Display results
        result_df = pd.DataFrame(results)
        st.success("✅ Calculation finished!")
        st.dataframe(result_df, use_container_width=True)

        # CSV download
        csv_bytes = result_df.to_csv(index=False).encode("utf-8")
        b64_csv = base64.b64encode(csv_bytes).decode()
        st.markdown(
            f'<a href="data:file/csv;base64,{b64_csv}" download="lane_results.csv">📥 Download CSV</a>',
            unsafe_allow_html=True,
        )

        # Excel download
        buf = io.BytesIO()
        with pd.ExcelWriter(buf, engine="xlsxwriter") as writer:
            result_df.to_excel(writer, index=False)
        b64_excel = base64.b64encode(buf.getvalue()).decode()
        st.markdown(
            f'<a href="data:application/vnd.openxmlformats-officedocument.spreadsheetml.sheet;base64,{b64_excel}" download="lane_results.xlsx">📥 Download Excel</a>',
            unsafe_allow_html=True,
        )
