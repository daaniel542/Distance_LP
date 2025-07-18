import os
from dotenv import load_dotenv
import time
import base64
import io

import streamlit as st
import pandas as pd
import pathlib

from lane_distance import get_candidates, geocode_primary
from geopy.distance import geodesic

load_dotenv()

# Page config
st.set_page_config(page_title="Lane Distance Calculator", page_icon="🛫", layout="wide")

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

# Sidebar: Info
st.sidebar.header("ℹ️ Network Info")
st.sidebar.markdown(
    """
    **Geocoding Service**: Mapbox API  
    **Rate Limits**: 1 req/sec, 2 retries  
    """
)

# Main UI
st.title("🛫 Lane Distance Calculator")
st.markdown(
    """
    Upload a CSV or Excel file with **Origin** and **Destination** columns,  
    then click **Calculate Distances**.
    """
)

uploaded = st.file_uploader("📂 Choose a file", type=["csv", "xls", "xlsx"])
if not uploaded:
    st.stop()

# Load data
suffix = pathlib.Path(uploaded.name).suffix.lower()
df = pd.read_excel(uploaded) if suffix in (".xls", ".xlsx") else pd.read_csv(uploaded)

st.subheader("📊 Data Preview")
st.dataframe(df.head())

if st.button("🚀 Calculate Distances"):
    total = len(df)
    start_time = time.time()

    # Placeholders for status text and progress bar
    status = st.empty()
    progress = st.progress(0)

    rows = []
    has_dist = "Distance_mi" in df.columns  # existing column from old runs

    for i, row in df.iterrows():
        elapsed = time.time() - start_time
        left = total - i

        status.text(f"Elapsed: {elapsed:.1f}s | Rows left: {left}")
        progress.progress((i + 1) / total)

        origin = row["Origin"]
        dest = row["Destination"]

        if has_dist and pd.notna(row.get("Distance_mi")):
            o_lat = row.get("origin_lat")
            o_lon = row.get("origin_lon")
            d_lat = row.get("destination_lat")
            d_lon = row.get("destination_lon")
            dist  = row.get("Distance_mi")
        else:
            o_lat, o_lon = geocode_primary(origin)
            d_lat, d_lon = geocode_primary(dest)
            if None not in (o_lat, o_lon, d_lat, d_lon):
                dist = geodesic((o_lat, o_lon), (d_lat, d_lon)).miles
            else:
                dist = None

        o_amb = len(get_candidates(origin)) > 1
        d_amb = len(get_candidates(dest)) > 1

        rows.append({
            "origin": origin,
            "destination": dest,
            "is_origin_ambiguous": o_amb,
            "is_destination_ambiguous": d_amb,
            "origin_latitude": o_lat,
            "origin_longitude": o_lon,
            "destination_latitude": d_lat,
            "destination_longitude": d_lon,
            "distance_miles": dist
        })

    progress.empty()
    status.empty()

    result = pd.DataFrame(rows)
    st.success("✅ Done calculating distances!")

    # --- Non-Ambiguous Entries ---
    nonambig_df = result[
        (~result["is_origin_ambiguous"]) &
        (~result["is_destination_ambiguous"])
    ]
    if not nonambig_df.empty:
        st.subheader("✅ Non-Ambiguous Entries")
        st.dataframe(nonambig_df)

        # Download links
        csv_bytes = nonambig_df.to_csv(index=False).encode("utf-8")
        b64_csv = base64.b64encode(csv_bytes).decode()
        st.markdown(
            f'<a href="data:file/csv;base64,{b64_csv}" download="nonambiguous_results.csv">'
            "📥 Download Non-Ambiguous Results (CSV)</a>",
            unsafe_allow_html=True
        )

        output = io.BytesIO()
        with pd.ExcelWriter(output, engine="xlsxwriter") as writer:
            nonambig_df.to_excel(writer, index=False)
        excel_bytes = output.getvalue()
        b64_xl = base64.b64encode(excel_bytes).decode()
        st.markdown(
            f'<a href="data:application/vnd.openxmlformats-officedocument.spreadsheetml.sheet;base64,{b64_xl}" '
            'download="nonambiguous_results.xlsx">📥 Download Non-Ambiguous Results (Excel)</a>',
            unsafe_allow_html=True
        )

    # --- Ambiguous Results Preview ---
    st.subheader("🔍 Ambiguous Results Preview")
    ambig_preview = result.head(5)
    st.dataframe(ambig_preview)

    csv_bytes = ambig_preview.to_csv(index=False).encode("utf-8")
    b64_csv = base64.b64encode(csv_bytes).decode()
    st.markdown(
        f'<a href="data:file/csv;base64,{b64_csv}" download="ambiguous_preview.csv">'
        "📥 Download Preview (CSV)</a>",
        unsafe_allow_html=True
    )

    output = io.BytesIO()
    with pd.ExcelWriter(output, engine="xlsxwriter") as writer:
        ambig_preview.to_excel(writer, index=False)
    excel_bytes = output.getvalue()
    b64_xl = base64.b64encode(excel_bytes).decode()
    st.markdown(
        f'<a href="data:application/vnd.openxmlformats-officedocument.spreadsheetml.sheet;base64,{b64_xl}" '
        'download="ambiguous_preview.xlsx">📥 Download Preview (Excel)</a>',
        unsafe_allow_html=True
    )

    # --- All Results ---
    with st.expander("📂 All Results"):
        st.dataframe(result)

        csv_bytes = result.to_csv(index=False).encode("utf-8")
        b64_csv = base64.b64encode(csv_bytes).decode()
        st.markdown(
            f'<a href="data:file/csv;base64,{b64_csv}" download="all_results.csv">'
            "📥 Download All Results (CSV)</a>",
            unsafe_allow_html=True
        )

        output = io.BytesIO()
        with pd.ExcelWriter(output, engine="xlsxwriter") as writer:
            result.to_excel(writer, index=False)
        excel_bytes = output.getvalue()
        b64_xl = base64.b64encode(excel_bytes).decode()
        st.markdown(
            f'<a href="data:application/vnd.openxmlformats-officedocument.spreadsheetml.sheet;base64,{b64_xl}" '
            'download="all_results.xlsx">📥 Download All Results (Excel)</a>',
            unsafe_allow_html=True
        )
