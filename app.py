import streamlit as st
import pandas as pd
from datetime import time
from parser import parse_g1gc_logs

st.set_page_config(page_title="GemFire GC Analyzer", layout="wide")
st.title("GemFire Garbage Collection Log Analyzer")

st.sidebar.header("Data Import")
uploaded_files = st.sidebar.file_uploader(
    "Upload GC Log Files",
    type=['log', 'txt'],
    accept_multiple_files=True
)

st.sidebar.header("Time Period Filter")
start_date = st.sidebar.date_input("Start Date", value=pd.to_datetime("2020-01-01"))
start_time = st.sidebar.time_input("Start Time", value=time(0, 0))
end_date = st.sidebar.date_input("End Date", value=pd.to_datetime("2030-12-31"))
end_time = st.sidebar.time_input("End Time", value=time(23, 59))

# Combine to datetimes
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