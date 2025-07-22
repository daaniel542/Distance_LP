import os
import time
import base64
import io
import pathlib

import streamlit as st
import pandas as pd

from lane_distance import resolve_place, great_circle, mapbox_distance
from dotenv import load_dotenv

load_dotenv()

st.set_page_config(page_title="Lane Distance Calculator", layout="wide")

# Sidebar README
README = pathlib.Path(__file__).parent / "README.MD"
if README.exists():
    st.sidebar.markdown(README.read_text())

st.title("🛫 Lane Distance Calculator")

# Upload
uploaded = st.file_uploader("Upload CSV or Excel", type=["csv", "xls", "xlsx"])
if not uploaded:
    st.info("Please upload a file to get started.")
else:
    # Load input
    df_in = (
        pd.read_excel(uploaded, dtype=str)
        if uploaded.name.lower().endswith((".xls", ".xlsx"))
        else pd.read_csv(uploaded, dtype=str)
    )

        # ------------------------------------------------------------------
    # File validity check
    # ------------------------------------------------------------------
    def has_col(df, name):
        return any(c.strip().lower() == name.lower() for c in df.columns)

    required_cols = ["Origin", "Destination"]
    all_present = all(has_col(df_in, col) for col in required_cols)
    status_msg = "Valid file" if all_present else "Invalid File"
    st.markdown(f"**{status_msg}**")

    # Detect optional LOCODE columns
    cols_l = [c.lower() for c in df_in.columns]
    origin_code_col = next(
        (c for lc, c in zip(cols_l, df_in.columns) if "origin" in lc and "locode" in lc),
        None
    )
    dest_code_col = next(
        (c for lc, c in zip(cols_l, df_in.columns)
         if ("dest" in lc or "destination" in lc) and "locode" in lc),
        None
    )

    # Calculate button
    if st.button("Calculate"):
        total = len(df_in)
        status = st.empty()
        prog = st.progress(0)
        results = []
        start = time.time()

        for idx, row in df_in.iterrows():
            elapsed = time.time() - start
            status.text(f"Elapsed: {elapsed:.1f}s | Rows left: {total - idx - 1}")
            prog.progress((idx + 1) / total)

            # Origin geocode
            name_o = row.get("Origin") or row.get("origin")
            code_o = row.get(origin_code_col) if origin_code_col else None
            try:
                lat_o, lon_o, amb_o, used_o = resolve_place(name_o, code_o)
                err_o = ""
            except Exception as e:
                lat_o = lon_o = None
                amb_o = True
                used_o = False
                err_o = str(e)

            # Destination geocode
            name_d = row.get("Destination") or row.get("destination")
            code_d = row.get(dest_code_col) if dest_code_col else None
            try:
                lat_d, lon_d, amb_d, used_d = resolve_place(name_d, code_d)
                err_d = ""
            except Exception as e:
                lat_d = lon_d = None
                amb_d = True
                used_d = False
                err_d = str(e)

            used_both = bool(used_o and used_d)
            if used_both:
                amb_o = amb_d = False

            # Distance
            distance = None
            error_msg = err_o or err_d or ""
            if not error_msg and None not in (lat_o, lon_o, lat_d, lon_d):
                if used_both:
                    distance = great_circle(lat_o, lon_o, lat_d, lon_d)
                else:
                    try:
                        distance = mapbox_distance(lat_o, lon_o, lat_d, lon_d)
                    except Exception:
                        distance = great_circle(lat_o, lon_o, lat_d, lon_d)

            results.append({
                "Origin": name_o,
                "Destination": name_d,
                "Origin LOCODE": code_o,
                "Destination LOCODE": code_d,
                "Origin latitude": lat_o,
                "Origin longitude": lon_o,
                "Destination latitude": lat_d,
                "Destination longitude": lon_d,
                "Distance_miles": distance,
                "Used UNLOCODEs": used_both,
                "Ambiguous Origin": amb_o,
                "Ambiguous Destination": amb_d,
                "Error_msg": error_msg
            })

        st.session_state.df_out = pd.DataFrame(results)
        st.success("✅ Calculation finished!")

    # If results exist, show table and controls
    if "df_out" in st.session_state:
        df_out = st.session_state.df_out

        # Show only issues toggle
        show_issues = st.checkbox("Show only issues", value=False)

        # APT/PT mask
        apt_pt_mask = (
            (~df_out["Used UNLOCODEs"]) & (
                df_out["Origin"].str.upper().fillna("").str.contains(r"\bAPT\b|\bPT\b", regex=True)
                | df_out["Destination"].str.upper().fillna("").str.contains(r"\bAPT\b|\bPT\b", regex=True)
            )
        )
        issue_mask = (
            df_out["Ambiguous Origin"]
            | df_out["Ambiguous Destination"]
            | df_out["Error_msg"].astype(bool)
            | apt_pt_mask
        )

        df_view = df_out[issue_mask] if show_issues else df_out

        # Highlight function
        def highlight_mapbox_apt(row):
            nm_o = (row["Origin"] or "").upper()
            nm_d = (row["Destination"] or "").upper()
            if not row["Used UNLOCODEs"] and ("APT" in nm_o or "PT" in nm_o or "APT" in nm_d or "PT" in nm_d):
                return ["background-color: yellow" if col == "Distance_miles" else "" for col in row.index]
            return ["" for _ in row.index]

        styled_df = df_view.style.apply(highlight_mapbox_apt, axis=1)
        st.dataframe(styled_df, use_container_width=True)

        # Downloads
        csv_b = df_out.to_csv(index=False).encode("utf-8")
        b64_csv = base64.b64encode(csv_b).decode()
        st.markdown(f'<a href="data:file/csv;base64,{b64_csv}" download="lane_results.csv">📥 Download CSV</a>', unsafe_allow_html=True)

        buf = io.BytesIO()
        with pd.ExcelWriter(buf, engine="xlsxwriter") as writer:
            df_out.to_excel(writer, index=False)
        b64_xl = base64.b64encode(buf.getvalue()).decode()
        st.markdown(f'<a href="data:application/vnd.openxmlformats-officedocument.spreadsheetml.sheet;base64,{b64_xl}" download="lane_results.xlsx">📥 Download Excel</a>', unsafe_allow_html=True)
