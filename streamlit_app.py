# streamlit_app.py
import os
from dotenv import load_dotenv
import time
load_dotenv()

import streamlit as st
import pandas as pd
from tempfile import NamedTemporaryFile
import pathlib

from lane_distance import get_candidates, geocode_primary
from geopy.distance import geodesic

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
        "text/csv" if sf.suffix.lower()==".csv" else
        "application/vnd.ms-excel" if sf.suffix.lower()==".xls" else
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

uploaded = st.file_uploader("📂 Choose a file", type=["csv","xls","xlsx"])
if not uploaded:
    st.stop()

# Load data
suffix = pathlib.Path(uploaded.name).suffix.lower()
df = pd.read_excel(uploaded) if suffix in (".xls",".xlsx") else pd.read_csv(uploaded)

st.subheader("📊 Data Preview")
st.dataframe(df.head())

if st.button("🚀 Calculate Distances"):
    total = len(df)
    start_time = time.time()
    status = st.empty()
    rows = []
    ambig = []
    nonambig = []

    # Determine if destination already present
    has_dest_cols = "destination_lat" in df.columns and "destination_lon" in df.columns

    for i, row in df.iterrows():
        elapsed = time.time() - start_time
        left = total - i
        status.text(f"Elapsed: {elapsed:.1f}s | Rows left: {left}")

        origin = row["Origin"]
        dest = row["Destination"]

        # Skip if destination coords already present
        if has_dest_cols and not pd.isna(row["destination_lat"]):
            o_lat = row.get("origin_lat")
            o_lon = row.get("origin_lon")
            d_lat = row["destination_lat"]
            d_lon = row["destination_lon"]
            dist = row.get("Distance_mi")
        else:
            o_lat, o_lon = geocode_primary(origin)
            d_lat, d_lon = geocode_primary(dest)
            dist = None
            if None not in (o_lat, o_lon, d_lat, d_lon):
                dist = geodesic((o_lat, o_lon), (d_lat, d_lon)).miles

        rows.append({
            "Origin": origin,
            "Destination": dest,
            "origin_lat": o_lat,
            "origin_lon": o_lon,
            "destination_lat": d_lat,
            "destination_lon": d_lon,
            "Distance_mi": dist
        })

        # Track ambiguity
        o_amb = len(get_candidates(origin)) > 1
        d_amb = len(get_candidates(dest)) > 1
        if o_amb or d_amb:
            ambig.append({
                "Row": i,
                "Origin": origin,
                "orig_ambiguous": o_amb,
                "Destination": dest,
                "dest_ambiguous": d_amb
            })
        else:
            nonambig.append({
                "Origin": origin,
                "Destination": dest,
                "origin_lat": o_lat,
                "origin_lon": o_lon,
                "destination_lat": d_lat,
                "destination_lon": d_lon,
                "Distance_mi": dist
            })

    result = pd.DataFrame(rows)
    st.success("✅ Done calculating distances!")

    # Full Results with expander
    st.subheader("Full Results")
    st.dataframe(result.head(5))
    with st.expander("Show all results"):
        st.dataframe(result)

    # Ambiguous Cities in expander
    if ambig:
        with st.expander("⚠️ Ambiguous Cities"):
            st.table(pd.DataFrame(ambig))
    else:
        st.info("No ambiguous cities detected.")

    # Non-Ambiguous Results table
    if nonambig:
        st.subheader("✅ Non-Ambiguous Results")
        st.dataframe(pd.DataFrame(nonambig))
    else:
        st.info("No non-ambiguous entries.")

    # Download buttons
    st.download_button(
        "📥 Download CSV",
        data=result.to_csv(index=False).encode("utf-8"),
        file_name="results.csv",
        mime="text/csv"
    )
    excel_tmp = NamedTemporaryFile(delete=False, suffix=".xlsx")
    pd.DataFrame(rows).to_excel(excel_tmp.name, index=False)
    with open(excel_tmp.name, "rb") as fp:
        st.download_button(
            "📥 Download Excel",
            data=fp.read(),
            file_name="results.xlsx",
            mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
        )