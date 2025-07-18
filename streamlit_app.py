import streamlit as st
import pandas as pd
from tempfile import NamedTemporaryFile
import pathlib
import os
from lane_distance import process_file

# ─── Page config ───────────────────────────────────────────────────────────────
st.set_page_config(
    page_title="Lane Distance Calculator",
    page_icon="🛫",
    layout="wide"
)

st.title("🛫 Lane Distance Calculator")
st.markdown(
    """
    Upload an Excel or CSV file containing **origin** and **destination** columns.
    This app will calculate crow-flight (“lane”) distances between each pair and
    let you download the results.
    """
)

# ─── File uploader & preview ───────────────────────────────────────────────────
uploaded_file = st.file_uploader(
    "Choose your Excel or CSV file",
    type=["xlsx", "xls", "csv"]
)

if uploaded_file is not None:
    st.success(f"File uploaded: **{uploaded_file.name}** ({uploaded_file.size:,} bytes)")

    # Preview first 5 rows
    try:
        if uploaded_file.name.lower().endswith((".xls", ".xlsx")):
            df_preview = pd.read_excel(uploaded_file, nrows=5)
        else:
            df_preview = pd.read_csv(uploaded_file, nrows=5)
    except Exception as e:
        st.error(f"❌ Failed to read preview: {e}")
        st.stop()

    st.subheader("📊 Data Preview (first 5 rows)")
    st.dataframe(df_preview)

    # Validate at least two columns
    if df_preview.shape[1] >= 2:
        st.success(f"✅ File validation passed! Found {df_preview.shape[1]} columns.")

        if st.button("🚀 Calculate Distances", type="primary"):
            with st.spinner("Processing... this may take a few minutes depending on network speed."):
                try:
                    # Write upload to a temp file so process_file can read/write
                    suffix = pathlib.Path(uploaded_file.name).suffix
                    with NamedTemporaryFile(delete=False, suffix=suffix) as tmp_in:
                        tmp_in.write(uploaded_file.getvalue())
                        tmp_in_path = pathlib.Path(tmp_in.name)

                    # Construct output path
                    tmp_out_path = tmp_in_path.with_name(f"{tmp_in_path.stem}_processed{tmp_in_path.suffix}")

                    # Run the core processing (uses your updated lane_distance.py)
                    result_df = process_file(tmp_in_path, tmp_out_path)

                    st.success("🎉 Processing completed!")

                    # Show metrics
                    total = len(result_df)
                    successful = result_df["lane_distance_mi"].notna().sum()
                    rate = (successful / total) * 100 if total > 0 else 0.0

                    col1, col2, col3 = st.columns(3)
                    col1.metric("Total Rows", total)
                    col2.metric("Successful Calculations", successful)
                    col3.metric("Success Rate", f"{rate:.1f}%")

                    # Show a sample of results
                    st.subheader("📋 Results (first 10 rows)")
                    st.dataframe(result_df.head(10))

                    if successful < total:
                        st.warning(
                            "⚠️ Some locations could not be geocoded. "
                            "Check for typos, network issues, or rate limits."
                        )

                    # Download processed file
                    with open(tmp_out_path, "rb") as f:
                        st.download_button(
                            label="📥 Download Processed File",
                            data=f.read(),
                            file_name=f"processed_{uploaded_file.name}",
                            mime="text/csv",
                        )

                    # Cleanup temp files
                    os.unlink(tmp_in_path)
                    os.unlink(tmp_out_path)

                except Exception as e:
                    st.error(f"❌ Error during processing: {e}")

    else:
        st.error("❌ Need at least two columns (origin, destination).")

# ─── Sample CSV download ───────────────────────────────────────────────────────
sample_path = pathlib.Path("sample_data.csv")
if sample_path.exists():
    st.markdown("---")
    st.markdown("### Try it out with a sample dataset")
    sample_bytes = sample_path.read_bytes()
    st.download_button(
        label="📄 Download Sample CSV",
        data=sample_bytes,
        file_name="sample_logistics_data.csv",
        mime="text/csv",
    )

# ─── Sidebar: network & rate-limit info ────────────────────────────────────────
st.sidebar.header("ℹ️ Network Info")
st.sidebar.markdown(
    """
    **Geocoding Service**: Mapbox Geocoding API  
    **Rate Limits**: 1 request per second, 2 retries on failure  
    **Requirements**:  
    - Internet connection required  
    - First run may be slower (populating cache)  
    """
)
