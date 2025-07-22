# streamlit_app.py

import os
import time
import base64
import io

import streamlit as st
import pandas as pd
import pathlib

from lane_distance import resolve_place, great_circle
from dotenv import load_dotenv

load_dotenv()

st.set_page_config(page_title="Lane Distance Calculator", page_icon="🛫", layout="wide")

# Sidebar instructions
README = pathlib.Path(__file__).parent / "README.MD"
st.sidebar.header("📖 Instructions")
if README.exists():
    st.sidebar.markdown(README.read_text())

st.title("🛫 Lane Distance Calculator")

uploaded = st.file_uploader("Upload CSV or Excel file", type=["csv", "xls", "xlsx"])

if uploaded:
    df = (
        pd.read_excel(uploaded)
        if uploaded.name.lower().endswith((".xls", ".xlsx"))
        else pd.read_csv(uploaded)
    )

    if st.button("Calculate"):
        start_time = time.time()
        total_rows = len(df)
        status = st.empty()
        progress = st.progress(0)

        results = []
        for idx, row in df.iterrows():
            elapsed = time.time() - start_time
            status.text(f"Elapsed: {elapsed:.1f}s | Rows left: {total_rows - idx - 1}")
            progress.progress((idx + 1) / total_rows)

            origin = row.get("Origin")
            destination = row.get("Destination")

            # Geocoding with error handling
            try:
                lat_o, lon_o, o_amb = resolve_place(origin)
                origin_error = None
            except Exception as e:
                lat_o = lon_o = None
                o_amb = True
                origin_error = str(e)

            try:
                lat_d, lon_d, d_amb = resolve_place(destination)
                dest_error = None
            except Exception as e:
                lat_d = lon_d = None
                d_amb = True
                dest_error = str(e)

            # Determine error and distance
            error_msg = origin_error or dest_error
            if error_msg:
                distance = None
            else:
                try:
                    distance = great_circle(lat_o, lon_o, lat_d, lon_d)
                except Exception as e:
                    distance = None
                    error_msg = str(e)

            results.append({
                "Origin": origin,
                "Destination": destination,
                "origin_lat": lat_o,
                "origin_lon": lon_o,
                "destination_lat": lat_d,
                "destination_lon": lon_d,
                "Distance_mi": distance,
                "is_origin_ambiguous": o_amb,
                "is_destination_ambiguous": d_amb,
                "error_msg": error_msg or ""
            })

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
        excel_buffer = io.BytesIO()
        with pd.ExcelWriter(excel_buffer, engine="xlsxwriter") as writer:
            result_df.to_excel(writer, index=False)
        b64_excel = base64.b64encode(excel_buffer.getvalue()).decode()
        st.markdown(
            f'<a href="data:application/vnd.openxmlformats-officedocument.spreadsheetml.sheet;base64,{b64_excel}" '
            'download="lane_results.xlsx">📥 Download Excel</a>',
            unsafe_allow_html=True,
        )
