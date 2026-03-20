import re
import pandas as pd
import io

def parse_g1gc_logs(uploaded_files, start_dt, end_dt, use_filter=True):
    pause_events = []
    concurrent_events = []
    cpu_events = []
    server_names = set() # To store unique server names found

    # regex updated to capture server name and GC ID
    # Format: [Timestamp][Uptime][ServerName][Level][Tags]
    pause_pattern = re.compile(
        r'\[(?P<timestamp>.*?)\]\[(?P<uptime>[\d\.]+)s\]\[(?P<server>.*?)\].*?GC\((?P<gc_id>\d+)\)\s+(?P<event>Pause.*?)\s+(?P<before>\d+)[A-Z]->(?P<after>\d+)[A-Z]\((?P<total>\d+)[A-Z]\)\s+(?P<duration>[\d\.]+)ms'
    )
    cpu_pattern = re.compile(r'GC\((?P<gc_id>\d+)\)\s+User=(?P<user>[\d\.]+)s\s+Sys=(?P<sys>[\d\.]+)s')
    concurrent_pattern = re.compile(r'GC\((?P<gc_id>\d+)\)\s+(?P<phase>Concurrent Mark Cycle|Concurrent Scan Root Regions).*?\s+(?P<duration>[\d\.]+)ms')

    # Basic metadata regex for server names if no pauses are found immediately
    server_meta_pattern = re.compile(r'^\[[^\]]+\]\[[^\]]+\]\[(?P<server>[^\]]+)\]')

    mem_t = {'region_size': 4, 'max_eden_peak': 0, 'max_eden_alloc': 0, 'max_surv_peak': 0, 'max_surv_alloc': 0, 'max_old_peak': 0, 'max_hum_peak': 0, 'max_meta_peak_k': 0, 'max_meta_alloc_k': 0}

    for file in uploaded_files:
        stringio = io.StringIO(file.getvalue().decode("utf-8", errors="ignore"))
        for line in stringio:
            # Grab server name from line header
            if not line.startswith('['): continue
            s_match = server_meta_pattern.search(line)
            if s_match:
                server_names.add(s_match.group('server'))

            # Memory Logic
            if "Eden regions" in line:
                m = re.search(r'Eden regions: (\d+)->\d+\((\d+)\)', line)
                if m:
                    mem_t['max_eden_peak'] = max(mem_t['max_eden_peak'], int(m.group(1)))
                    mem_t['max_eden_alloc'] = max(mem_t['max_eden_alloc'], int(m.group(2)))
            elif "Survivor regions" in line:
                m = re.search(r'Survivor regions: (\d+)->\d+\((\d+)\)', line)
                if m:
                    mem_t['max_surv_peak'] = max(mem_t['max_surv_peak'], int(m.group(1)))
                    mem_t['max_surv_alloc'] = max(mem_t['max_surv_alloc'], int(m.group(2)))
            elif "Old regions" in line:
                m = re.search(r'Old regions: (\d+)->(\d+)', line)
                if m: mem_t['max_old_peak'] = max(mem_t['max_old_peak'], int(m.group(1)), int(m.group(2)))
            elif "Humongous regions" in line:
                m = re.search(r'Humongous regions: (\d+)->(\d+)', line)
                if m: mem_t['max_hum_peak'] = max(mem_t['max_hum_peak'], int(m.group(1)), int(m.group(2)))
            elif "Metaspace" in line and "(" in line:
                m = re.search(r'Metaspace: (\d+)K\((\d+)K\)', line)
                if m:
                    mem_t['max_meta_peak_k'] = max(mem_t['max_meta_peak_k'], int(m.group(1)))
                    mem_t['max_meta_alloc_k'] = max(mem_t['max_meta_alloc_k'], int(m.group(2)))

            cpu_m = cpu_pattern.search(line)
            if cpu_m:
                ts_str = line.split(']')[0].replace('[', '')
                cpu_events.append({'gc_id': cpu_m.group('gc_id'), 'timestamp': pd.to_datetime(ts_str).tz_localize(None), 'cpu_ms': (float(cpu_m.group('user')) + float(cpu_m.group('sys'))) * 1000})

            pause_m = pause_pattern.search(line)
            if pause_m:
                ts = pd.to_datetime(pause_m.group('timestamp')).tz_localize(None)
                event_str = pause_m.group('event')
                pause_events.append({
                    'gc_id': pause_m.group('gc_id'),
                    'timestamp': ts, 'event': event_str,
                    'is_evacuation': "(G1 Evacuation Pause)" in event_str,
                    'cause': event_str.split("(")[-1].replace(")", "").strip() if "(" in event_str else "Unknown",
                    'mem_before_mb': int(pause_m.group('before')), 'mem_after_mb': int(pause_m.group('after')),
                    'mem_total_mb': int(pause_m.group('total')), 'duration_ms': float(pause_m.group('duration'))
                })

            con_m = concurrent_pattern.search(line)
            if con_m:
                ts_str = line.split(']')[0].replace('[', '')
                concurrent_events.append({'gc_id': con_m.group('gc_id'), 'timestamp': pd.to_datetime(ts_str).tz_localize(None), 'phase': con_m.group('phase'), 'duration_ms': float(con_m.group('duration'))})

    df_p = pd.DataFrame(pause_events)
    df_c = pd.DataFrame(concurrent_events)
    df_cpu = pd.DataFrame(cpu_events)

    if not df_p.empty:
        df_p = df_p.sort_values('duration_ms', ascending=False).drop_duplicates(subset=['gc_id'])
    if not df_c.empty:
        df_c = df_c.sort_values('duration_ms', ascending=False).drop_duplicates(subset=['gc_id', 'phase'])
    if not df_cpu.empty:
        df_cpu = df_cpu.drop_duplicates(subset=['gc_id'])

    raw_count = len(df_p)

    if not df_p.empty and use_filter:
        df_p = df_p[(df_p['timestamp'] >= start_dt) & (df_p['timestamp'] <= end_dt)]
    if not df_c.empty and use_filter:
        df_c = df_c[(df_c['timestamp'] >= start_dt) & (df_c['timestamp'] <= end_dt)]
    if not df_cpu.empty and use_filter:
        df_cpu = df_cpu[(df_cpu['timestamp'] >= start_dt) & (df_cpu['timestamp'] <= end_dt)]

    if df_p.empty:
        return {
            "debug_info": {"raw_found": raw_count, "filtered_found": 0},
            "server_list": list(server_names)
        }

    runtime_s = (df_p['timestamp'].max() - df_p['timestamp'].min()).total_seconds()
    total_cpu_ms = df_cpu['cpu_ms'].sum() if not df_cpu.empty else 0

    result = generate_dashboard_data(df_p, df_c, runtime_s, mem_t, total_cpu_ms)
    result["debug_info"] = {"raw_found": raw_count, "filtered_found": len(df_p)}
    result["server_list"] = list(server_names)
    return result

def format_time_str(ms):
    if pd.isna(ms) or ms <= 0: return "0 ms"
    if ms < 1000: return f"{ms:.2f} ms"
    s, ms_rem = divmod(ms, 1000)
    m, s = divmod(int(s), 60)
    res = f"{m} min {s} sec" if m > 0 else f"{s} sec"
    if ms_rem > 0: res += f" {ms_rem:.0f} ms"
    return res

def get_major_phase_stats(df, label, runtime_ms):
    if df is None or df.empty: return {label: ["0", "0", "0", "0", "0", "0", "0"]}
    dur = df['duration_ms']
    cnt = len(dur)
    return {label: [format_time_str(dur.sum()), format_time_str(dur.mean()), format_time_str(dur.std() if cnt > 1 else 0),
                    format_time_str(dur.min()), format_time_str(dur.max()), format_time_str(runtime_ms / cnt if cnt > 0 else 0), str(cnt)]}

def generate_dashboard_data(df_p, df_c, runtime_s, mem, total_cpu_ms):
    runtime_ms = runtime_s * 1000
    throughput = (1 - (df_p['duration_ms'].sum() / runtime_ms)) * 100 if runtime_ms > 0 else 100
    df_evac = df_p[df_p['is_evacuation'] == True]

    rs = mem['region_size']
    young_peak = (mem['max_eden_peak'] + mem['max_surv_peak']) * rs
    young_alloc = (mem['max_eden_alloc'] + mem['max_surv_alloc']) * rs
    old_peak, old_alloc = mem['max_old_peak'] * rs, (df_p['mem_total_mb'].max() - young_alloc)
    meta_peak, meta_alloc = mem['max_meta_peak_k'] / 1024, mem['max_meta_alloc_k'] / 1024

    jvm_stats = pd.DataFrame({
        "Generation": ["Young Generation", "Old Generation", "Humongous", "Meta Space", "Total (Heap+Meta)"],
        "Allocated": [format_mem(young_alloc), format_mem(old_alloc), "n/a", format_mem(meta_alloc), format_mem(df_p['mem_total_mb'].max() + meta_alloc)],
        "Peak": [format_mem(young_peak), format_mem(old_peak), format_mem(mem['max_hum_peak']*rs), format_mem(meta_peak), format_mem(young_peak+old_peak+meta_peak)]
    })

    chart_data = pd.DataFrame([
        {"Type": "allocated", "Generation": "Young GC", "Value (GB)": round(young_alloc/1024,3)},
        {"Type": "allocated", "Generation": "Old Gen", "Value (GB)": round(old_alloc/1024,3)},
        {"Type": "allocated", "Generation": "Meta Space", "Value (GB)": round(meta_alloc/1024,3)},
        {"Type": "peak usage", "Generation": "Young GC", "Value (GB)": round(young_peak/1024,3)},
        {"Type": "peak usage", "Generation": "Old Gen", "Value (GB)": round(old_peak/1024,3)},
        {"Type": "peak usage", "Generation": "Humongous Gen", "Value (GB)": round(mem['max_hum_peak']*rs/1024,3)},
        {"Type": "peak usage", "Generation": "Meta Space", "Value (GB)": round(meta_peak/1024,3)},
    ])
    chart_data['Text'] = chart_data['Value (GB)'].apply(lambda x: f"{x:.2f}gb" if x > 0 else "")

    bins = [0, 100, 200, 300, 400, 500, 600, float('inf')]
    labels = ['0-100','100-200','200-300','300-400','400-500','500-600','600+']
    df_evac_copy = df_evac.copy()
    if not df_evac_copy.empty:
        df_evac_copy['bucket'] = pd.cut(df_evac_copy['duration_ms'], bins=bins, labels=labels, right=False)
        pause_dist = df_evac_copy['bucket'].value_counts().reset_index().rename(columns={'count': 'No. of GCs', 'bucket': 'Duration (ms)'}).sort_values('Duration (ms)')
        pause_dist['Percentage'] = (pause_dist['No. of GCs'] / len(df_evac) * 100).apply(lambda x: f"{x:.2f}%")
    else:
        pause_dist = pd.DataFrame(columns=['Duration (ms)', 'No. of GCs', 'Percentage'])

    stats_dict = {"": ["Total Time", "Avg Time", "Std Dev Time", "Min Time", "Max Time", "Interval Time", "Count"]}
    stats_dict.update(get_major_phase_stats(df_p[df_p['event'].str.contains('Young')], "Young GC", runtime_ms))
    stats_dict.update(get_major_phase_stats(df_c[df_c['phase'].str.contains('Mark')], "Concurrent Marking", runtime_ms))
    stats_dict.update(get_major_phase_stats(df_c[df_c['phase'].str.contains('Scan')], "Root Region Scanning", runtime_ms))
    stats_dict.update(get_major_phase_stats(df_p[df_p['event'].str.contains('Remark')], "Remark", runtime_ms))
    stats_dict.update(get_major_phase_stats(df_p[df_p['event'].str.contains('Cleanup')], "Cleanup", runtime_ms))

    return {
        "throughput": round(throughput, 4), "total_runtime_str": f"{runtime_s / 3600:.2f} hrs" if runtime_s > 3600 else f"{runtime_s:.2f} sec",
        "cpu_time_str": format_time_str(total_cpu_ms), "avg_pause": format_time_str(df_evac['duration_ms'].mean()) if not df_evac.empty else "0 ms",
        "max_pause": format_time_str(df_evac['duration_ms'].max()) if not df_evac.empty else "0 ms",
        "jvm_memory_stats": jvm_stats, "memory_chart_data": chart_data,
        "pause_distribution": pause_dist, "gc_causes": df_evac.groupby('cause')['duration_ms'].count().reset_index().rename(columns={'duration_ms': 'Count', 'cause': 'Cause'}),
        "major_phase_stats": pd.DataFrame(stats_dict), "heap_chart_data": df_p[['timestamp', 'mem_after_mb', 'mem_total_mb']].copy().set_index('timestamp').rename(columns={'mem_after_mb': 'Used Heap (MB)', 'mem_total_mb': 'Total Heap (MB)'})
    }

def format_mem(mb):
    if pd.isna(mb) or mb <= 0: return "0 mb"
    return f"{mb / 1024:.2f} gb" if mb >= 1024 else f"{mb:.2f} mb"