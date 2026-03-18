import streamlit as st
import pandas as pd
from datetime import time
import re
from parser import parse_g1gc_logs

st.set_page_config(page_title="GemFire GC Analyzer", layout="wide")
st.title("GemFire Garbage Collection Log Analyzer")

st.sidebar.header("Data Import")
uploaded_files = st.sidebar.file_uploader(
    "Upload GC Log Files",
    type=['log', 'txt'],
    accept_multiple_files=True
)

# --- NEW: Helper function to dynamically extract min/max dates from logs ---
def get_log_time_range(files):
    min_dt = None
    max_dt = None
    # Regex to match the ISO 8601 timestamp at the start of a Unified JVM log line
    ts_pattern = re.compile(r'^\[(\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}\.\d{3}[+-]\d{4})\]')

    for file in files:
        # Read file content efficiently from Streamlit's memory buffer
        content = file.getvalue().decode("utf-8").splitlines()
        if not content:
            continue

        # Scan top-down for the very first timestamp
        for line in content:
            match = ts_pattern.search(line)
            if match:
                dt = pd.to_datetime(match.group(1)).tz_localize(None)
                if min_dt is None or dt < min_dt:
                    min_dt = dt
                break

        # Scan bottom-up for the very last timestamp
        for line in reversed(content):
            match = ts_pattern.search(line)
            if match:
                dt = pd.to_datetime(match.group(1)).tz_localize(None)
                if max_dt is None or dt > max_dt:
                    max_dt = dt
                break

    return min_dt, max_dt

# Default fallbacks if no files are uploaded yet
default_start_date = pd.to_datetime("2020-01-01").date()
default_start_time = time(0, 0)
default_end_date = pd.to_datetime("2030-12-31").date()
default_end_time = time(23, 59)

# If files are uploaded, update the defaults dynamically
if uploaded_files:
    min_dt, max_dt = get_log_time_range(uploaded_files)
    if min_dt and max_dt:
        default_start_date = min_dt.date()
        default_start_time = min_dt.time()
        default_end_date = max_dt.date()
        default_end_time = max_dt.time()

st.sidebar.header("Time Period Filter")
# The value parameters here now use our dynamic defaults!
start_date = st.sidebar.date_input("Start Date", value=default_start_date)
start_time = st.sidebar.time_input("Start Time", value=default_start_time)
end_date = st.sidebar.date_input("End Date", value=default_end_date)
end_time = st.sidebar.time_input("End Time", value=default_end_time)

# Combine to datetimes for the parser filtering
start_datetime = pd.to_datetime(f"{start_date} {start_time}")
end_datetime = pd.to_datetime(f"{end_date} {end_time}")

if uploaded_files:
    data = parse_g1gc_logs(uploaded_files, start_datetime, end_datetime)

    if data:
        st.success(f"Successfully loaded and filtered {len(uploaded_files)} file(s).")

        # Line Chart
        st.subheader("Heap Usage Over Time")
        st.line_chart(data['heap_chart_data'])

        st.divider()

        # KPIs
        st.header("KPIs")
        col1, col2, col3, col4 = st.columns(4)
        col1.metric("Throughput", f"{data['throughput']}%")
        col2.metric("Total Runtime", data['cpu_time'])
        col3.metric("Avg Pause GC Time", data['avg_pause'])
        col4.metric("Max Pause GC Time", data['max_pause'])

        st.divider()

        # Memory & Causes
        col_mem, col_cause = st.columns(2)
        with col_mem:
            st.subheader("Memory Allocation")
            st.dataframe(data['memory_stats'], hide_index=True, use_container_width=True)

        with col_cause:
            st.subheader("GC Causes")
            st.dataframe(data['gc_causes'], hide_index=True, use_container_width=True)

        st.divider()

        # Distributions & Phases
        col_dist, col_phase = st.columns(2)
        with col_dist:
            st.subheader("Pause Duration Time Range")
            st.dataframe(data['pause_distribution'], hide_index=True, use_container_width=True)

        with col_phase:
            st.subheader("GC Phase Statistics")
            if not data['phase_stats'].empty:
                st.dataframe(data['phase_stats'], hide_index=True, use_container_width=True)
    else:
        st.warning("No data found for the selected time period. Please adjust your filters.")
else:
    st.info("Please upload GemFire GC log files from the sidebar to begin analysis.")