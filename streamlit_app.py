import os
import time
import base64
import io
import pathlib

import streamlit as st
import pandas as pd

# resolve_place now returns (lat, lon, ambiguous, used_unlocode, source)
from lane_distance import resolve_place, great_circle, mapbox_distance
from dotenv import load_dotenv

load_dotenv()

st.set_page_config(page_title="Lane Distance Calculator", layout="wide")

# Sidebar README
README = pathlib.Path(__file__).parent / "README.MD"
if README.exists():
    st.sidebar.markdown(README.read_text())

st.title("🛫Lane Distance Calculator")

uploaded = st.file_uploader("Upload CSV or Excel", type=["csv", "xls", "xlsx"])
if not uploaded:
    st.info("Please upload a file to get started.")
else:
    # If this is a new upload, reset previous results
    if (
        "uploaded_name" not in st.session_state
        or st.session_state.uploaded_name != uploaded.name
    ):
        st.session_state.uploaded_name = uploaded.name
        st.session_state.df_out = None

    # ─────────────────────────────────────────────────────────────────
    # Load the input file
    # ─────────────────────────────────────────────────────────────────
    df_in = (
        pd.read_excel(uploaded, dtype=str)
        if uploaded.name.lower().endswith((".xls", ".xlsx"))
        else pd.read_csv(uploaded, dtype=str)
    )

    # ─────────────────────────────────────────────────────────────────
    # File-level validator: Origin & Destination must both exist
    # ─────────────────────────────────────────────────────────────────
    def has_col(df, name):
        return any(c.strip().lower() == name.lower() for c in df.columns)

    required_cols = ["Origin", "Destination"]
    is_valid = all(has_col(df_in, col) for col in required_cols)

    if is_valid:
        st.success("✅ Valid file")
    else:
        st.error("❌ Invalid file: must include both Origin and Destination columns")

    # ─────────────────────────────────────────────────────────────────
    # Detect optional LOCODE columns
    # ─────────────────────────────────────────────────────────────────
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

    # ─────────────────────────────────────────────────────────────────
    # Run calculation when user clicks (disabled if file invalid)
    # ─────────────────────────────────────────────────────────────────
    if st.button("Calculate", disabled=not is_valid):
        total = len(df_in)
        status = st.empty()
        prog = st.progress(0)
        results = []
        start = time.time()

        for idx, row in df_in.iterrows():
            elapsed = time.time() - start
            status.text(f"Elapsed: {elapsed:.1f}s | Rows left: {total - idx - 1}")
            prog.progress((idx + 1) / total)

            # Geocode origin
            name_o = row.get("Origin") or row.get("origin")
            code_o = row.get(origin_code_col) if origin_code_col else None
            try:
                lat_o, lon_o, amb_o, used_o, src_o = resolve_place(name_o, code_o)
                err_o = ""
            except Exception as e:
                lat_o = lon_o = None
                amb_o = True
                used_o = False
                src_o = None
                err_o = str(e)

            # Geocode destination
            name_d = row.get("Destination") or row.get("destination")
            code_d = row.get(dest_code_col) if dest_code_col else None
            try:
                lat_d, lon_d, amb_d, used_d, src_d = resolve_place(name_d, code_d)
                err_d = ""
            except Exception as e:
                lat_d = lon_d = None
                amb_d = True
                used_d = False
                src_d = None
                err_d = str(e)

            # Unambiguous if both LOCODEs used
            used_both = bool(used_o and used_d)
            if used_both:
                amb_o = amb_d = False

            # Determine record-level source
            if src_o == src_d:
                source = src_o or ""
            else:
                source = ",".join(filter(None, [src_o, src_d]))

            # Distance calc
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
                "Source": source,
                "Ambiguous Origin": amb_o,
                "Ambiguous Destination": amb_d,
                "Error_msg": error_msg
            })

        st.session_state.df_out = pd.DataFrame(results)
        st.success("✅ Calculation finished!")

    # ─────────────────────────────────────────────────────────────────
    # Display and filter results if available
    # ─────────────────────────────────────────────────────────────────
    if st.session_state.get("df_out") is not None:
        df_out = st.session_state.df_out

        # Show-only-issues toggle
        show_issues = st.checkbox("Show only issues", value=False)
        apt_pt_mask = (
            (~df_out["Used UNLOCODEs"])
            & (
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

        # Highlight APT/PT Mapbox distances
        def highlight_mapbox_apt(row):
            name_o = (row["Origin"] or "").upper()
            name_d = (row["Destination"] or "").upper()
            if (
                not row["Used UNLOCODEs"]
                and ("APT" in name_o or "PT" in name_o or "APT" in name_d or "PT" in name_d)
            ):
                return [
                    "background-color: yellow" if col == "Distance_miles" else ""
                    for col in row.index
                ]
            return ["" for _ in row.index]

        styled = df_view.style.apply(highlight_mapbox_apt, axis=1)
        st.dataframe(styled, use_container_width=True)

        # CSV download
        csv_bytes = df_out.to_csv(index=False).encode("utf-8")
        b64_csv = base64.b64encode(csv_bytes).decode()
        st.markdown(
            f'<a href="data:file/csv;base64,{b64_csv}" download="lane_results.csv">📥 Download CSV</a>',
            unsafe_allow_html=True,
        )

        # Excel download
        buf = io.BytesIO()
        with pd.ExcelWriter(buf, engine="xlsxwriter") as writer:
            df_out.to_excel(writer, index=False)
        b64_xl = base64.b64encode(buf.getvalue()).decode()
        st.markdown(
            f'<a href="data:application/vnd.openxmlformats-officedocument.spreadsheetml.sheet;base64,{b64_xl}" '
            f'download="lane_results.xlsx">📥 Download Excel</a>',
            unsafe_allow_html=True,
        )
