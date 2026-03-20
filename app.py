import streamlit as st
import pandas as pd
import plotly.express as px
from datetime import time
import re
from parser import parse_g1gc_logs

st.set_page_config(page_title="GemFire GC Analyzer", layout="wide")

# Sidebar for file upload and filters
st.sidebar.header("1. Data Import")
uploaded_files = st.sidebar.file_uploader("Upload GC Log Files", type=['log', 'txt'], accept_multiple_files=True)

def get_log_time_range(files):
    min_dt, max_dt = None, None
    ts_pattern = re.compile(r'^\[(\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}\.\d{3}.*?)\]')
    for file in files:
        lines = file.getvalue().decode("utf-8", errors="ignore").splitlines()
        for line in lines:
            m = ts_pattern.search(line)
            if m:
                dt = pd.to_datetime(m.group(1)).tz_localize(None)
                min_dt = dt if min_dt is None or dt < min_dt else min_dt
                break
        for line in reversed(lines):
            m = ts_pattern.search(line)
            if m:
                dt = pd.to_datetime(m.group(1)).tz_localize(None)
                max_dt = dt if max_dt is None or dt > max_dt else max_dt
                break
    return min_dt, max_dt

d_start, t_start = pd.to_datetime("2020-01-01").date(), time(0, 0)
d_end, t_end = pd.to_datetime("2030-12-31").date(), time(23, 59)

if uploaded_files:
    min_dt, max_dt = get_log_time_range(uploaded_files)
    if min_dt and max_dt:
        d_start, t_start = min_dt.date(), min_dt.time()
        d_end, t_end = max_dt.date(), max_dt.time()

st.sidebar.header("2. Filtering")
enable_filter = st.sidebar.checkbox("Enable Time Filter", value=True)
start_d = st.sidebar.date_input("Start Date", value=d_start)
start_t = st.sidebar.time_input("Start Time", value=t_start)
end_d = st.sidebar.date_input("End Date", value=d_end)
end_t = st.sidebar.time_input("End Time", value=t_end)

if uploaded_files:
    start_dt = pd.to_datetime(f"{start_d} {start_t}")
    end_dt = pd.to_datetime(f"{end_d} {end_t}")

    data = parse_g1gc_logs(uploaded_files, start_dt, end_dt, use_filter=enable_filter)

    # --- NEW: Dynamic Title with Server Name(s) ---
    servers = data.get("server_list", [])
    if servers:
        server_str = ", ".join(servers)
        st.title(f"GemFire GC Analyzer: {server_str}")
    else:
        st.title("GemFire Garbage Collection Log Analyzer")

    with st.sidebar.expander("🔍 Parser Debug Info"):
        if "debug_info" in data:
            st.write(f"Raw GC Pauses found: {data['debug_info']['raw_found']}")
            st.write(f"After time filter: {data['debug_info']['filtered_found']}")

    if "jvm_memory_stats" in data:
        st.success(f"Successfully analyzed {len(uploaded_files)} file(s).")
        st.subheader("Heap Usage Over Time")
        st.line_chart(data['heap_chart_data'])
        st.divider()

        st.header("KPIs")
        c1, c2, c3, c4, c5 = st.columns(5)
        c1.metric("Throughput", f"{data['throughput']}%")
        c2.metric("Selection Runtime", data['total_runtime_str'])
        c3.metric("GC CPU Time (User+Sys)", data['cpu_time_str'])
        c4.metric("Avg Pause", data['avg_pause'])
        c5.metric("Max Pause", data['max_pause'])

        st.divider()
        st.subheader("JVM Memory Size")
        st.dataframe(data['jvm_memory_stats'], hide_index=True, use_container_width=True)
        fig = px.bar(data['memory_chart_data'], x="Value (GB)", y="Type", color="Generation", orientation='h', text="Text",
                     color_discrete_map={"Young GC": "#1EAFAD", "Old Gen": "#151F4B", "Humongous Gen": "#917E91", "Meta Space": "#91C85A"})
        fig.update_layout(barmode='stack', yaxis={'title': '', 'categoryorder': 'array', 'categoryarray': ['peak usage', 'allocated']}, height=250)
        st.plotly_chart(fig, use_container_width=True)

        st.divider()
        col_cause, col_dist = st.columns(2)
        with col_cause:
            st.subheader("GC Causes")
            st.dataframe(data['gc_causes'], hide_index=True, use_container_width=True)
        with col_dist:
            st.subheader("Pause Duration Distribution")
            st.dataframe(data['pause_distribution'], hide_index=True, use_container_width=True)

        st.divider()
        st.subheader("GC Phase Statistics")
        st.dataframe(data['major_phase_stats'], hide_index=True, use_container_width=True)
    else:
        st.warning("No GC data found for the selected time period.")
else:
    st.title("GemFire Garbage Collection Log Analyzer")
    st.info("Please upload GemFire GC log files to begin.")