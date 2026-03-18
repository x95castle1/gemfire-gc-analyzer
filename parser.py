import re
import pandas as pd
import io

def parse_g1gc_logs(uploaded_files, start_dt, end_dt):
    pause_events = []
    phase_events = []
    last_uptime = 0.0

    pause_pattern = re.compile(
        r'\[(?P<timestamp>[^\]]+)\]\[(?P<uptime>[\d\.]+)s\].*?GC\(\d+\)\s+(?P<event>Pause.*?)\s+(?P<before>\d+)[A-Z]->(?P<after>\d+)[A-Z]\((?P<total>\d+)[A-Z]\)\s+(?P<duration>[\d\.]+)ms'
    )

    phase_pattern = re.compile(
        r'\[(?P<timestamp>[^\]]+)\]\[(?P<uptime>[\d\.]+)s\].*?GC\(\d+\)\s+(?P<phase>[A-Za-z ][A-Za-z0-9 ]+):\s+(?P<duration>[\d\.]+)ms'
    )

    for file in uploaded_files:
        stringio = io.StringIO(file.getvalue().decode("utf-8"))
        for line in stringio:
            uptime_match = re.search(r'\[([\d\.]+)s\]', line)
            if uptime_match:
                last_uptime = max(last_uptime, float(uptime_match.group(1)))

            pause_match = pause_pattern.search(line)
            if pause_match:
                event_string = pause_match.group('event')
                cause = "Unknown"
                if "(" in event_string and ")" in event_string:
                    cause = event_string.split("(")[-1].replace(")", "").strip()

                pause_events.append({
                    'timestamp': pd.to_datetime(pause_match.group('timestamp')),
                    'uptime_s': float(pause_match.group('uptime')),
                    'event': event_string,
                    'cause': cause,
                    'mem_before_mb': int(pause_match.group('before')),
                    'mem_after_mb': int(pause_match.group('after')),
                    'mem_total_mb': int(pause_match.group('total')),
                    'duration_ms': float(pause_match.group('duration'))
                })
                continue

            phase_match = phase_pattern.search(line)
            if phase_match:
                phase_events.append({
                    'timestamp': pd.to_datetime(phase_match.group('timestamp')),
                    'uptime_s': float(phase_match.group('uptime')),
                    'phase': phase_match.group('phase').strip(),
                    'duration_ms': float(phase_match.group('duration'))
                })

    df_pauses = pd.DataFrame(pause_events)
    df_phases = pd.DataFrame(phase_events)

    # Apply Time Filters
    if not df_pauses.empty:
        df_pauses['timestamp'] = df_pauses['timestamp'].dt.tz_localize(None)
        df_pauses = df_pauses[(df_pauses['timestamp'] >= start_dt) & (df_pauses['timestamp'] <= end_dt)]

    if not df_phases.empty:
        df_phases['timestamp'] = df_phases['timestamp'].dt.tz_localize(None)
        df_phases = df_phases[(df_phases['timestamp'] >= start_dt) & (df_phases['timestamp'] <= end_dt)]

    if df_pauses.empty:
        return None

    return generate_dashboard_data(df_pauses, df_phases, last_uptime)


def generate_dashboard_data(df_pauses, df_phases, total_runtime_s):
    total_pause_ms = df_pauses['duration_ms'].sum()
    total_runtime_ms = total_runtime_s * 1000

    throughput = 100.0
    if total_runtime_ms > 0:
        throughput = (1 - (total_pause_ms / total_runtime_ms)) * 100

    avg_pause = df_pauses['duration_ms'].mean()
    max_pause = df_pauses['duration_ms'].max()

    max_allocated = df_pauses['mem_total_mb'].max()
    peak_used = df_pauses['mem_before_mb'].max()

    memory_stats = pd.DataFrame({
        "Region": ["Heap Size"],
        "Allocated": [f"{max_allocated / 1024:.2f} GB"],
        "Peak": [f"{peak_used / 1024:.2f} GB"]
    })

    gc_causes = df_pauses.groupby('cause').agg(
        Count=('duration_ms', 'count'),
        Avg_Time=('duration_ms', 'mean'),
        Max_Time=('duration_ms', 'max'),
        Total_Time=('duration_ms', 'sum')
    ).reset_index()

    gc_causes['Avg_Time'] = gc_causes['Avg_Time'].apply(lambda x: f"{x:.0f} ms")
    gc_causes['Max_Time'] = gc_causes['Max_Time'].apply(lambda x: f"{x:.0f} ms")
    gc_causes['Total_Time'] = gc_causes['Total_Time'].apply(lambda x: f"{x/1000:.2f} s")
    gc_causes.rename(columns={'cause': 'Cause'}, inplace=True)

    bins = [0, 100, 200, 300, 400, 500, 600, float('inf')]
    labels = ['0 - 100', '100 - 200', '200 - 300', '300 - 400', '400 - 500', '500 - 600', '600+']
    df_pauses['bucket'] = pd.cut(df_pauses['duration_ms'], bins=bins, labels=labels, right=False)

    pause_dist = df_pauses['bucket'].value_counts().reset_index()
    pause_dist.columns = ['Duration (ms)', 'No. of GCs']
    pause_dist['Percentage'] = (pause_dist['No. of GCs'] / len(df_pauses) * 100).apply(lambda x: f"{x:.2f}%")
    pause_dist = pause_dist.sort_values('Duration (ms)')

    # Phase Statistics
    phase_stats = pd.DataFrame()
    if not df_phases.empty:
        phase_stats = df_phases.groupby('phase').agg(
            Total_Time=('duration_ms', 'sum'),
            Avg_Time=('duration_ms', 'mean'),
            Std_Dev_Time=('duration_ms', 'std'),
            Min_Time=('duration_ms', 'min'),
            Max_Time=('duration_ms', 'max'),
            Count=('duration_ms', 'count')
        ).reset_index()

        phase_stats['Std_Dev_Time'] = phase_stats['Std_Dev_Time'].fillna(0)
        phase_stats = phase_stats.round(2)

        for col in ['Total_Time', 'Avg_Time', 'Std_Dev_Time', 'Min_Time', 'Max_Time']:
            phase_stats[col] = phase_stats[col].astype(str) + " ms"

    # Line Chart Data (Heap)
    heap_chart_data = df_pauses[['timestamp', 'mem_after_mb', 'mem_total_mb']].copy()
    heap_chart_data.set_index('timestamp', inplace=True)
    heap_chart_data.rename(columns={'mem_after_mb': 'Used Heap (MB)', 'mem_total_mb': 'Total Heap (MB)'}, inplace=True)

    return {
        "throughput": round(throughput, 3),
        "cpu_time": f"{total_runtime_s / 3600:.2f} hrs",
        "avg_pause": f"{avg_pause:.0f} ms",
        "max_pause": f"{max_pause:.0f} ms",
        "memory_stats": memory_stats,
        "pause_distribution": pause_dist,
        "gc_causes": gc_causes,
        "phase_stats": phase_stats,
        "heap_chart_data": heap_chart_data
    }