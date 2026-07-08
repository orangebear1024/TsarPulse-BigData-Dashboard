"""
TsarPulse — Flask Backend API
Provides /api/metrics with optional ?hostid= filter.
Aggregates raw TSAR data from MySQL in real time.
"""
from flask import Flask, request, jsonify, send_from_directory
from sqlalchemy import create_engine, text
import os

app = Flask(__name__, static_folder='.', static_url_path='')

# ── DB Config ──────────────────────────────────────────────
DB_CONFIG = {
    'host': 'localhost',
    'port': 3306,
    'user': 'root',
    'password': '123456',
    'charset': 'utf8mb4',
}
DB_NAME = 'tsar_pulse'

engine = create_engine(
    f"mysql+pymysql://{DB_CONFIG['user']}:{DB_CONFIG['password']}@"
    f"{DB_CONFIG['host']}:{DB_CONFIG['port']}/{DB_NAME}"
    f"?charset={DB_CONFIG['charset']}",
    pool_size=5,
    pool_recycle=3600,
)

# ── Tag labels ─────────────────────────────────────────────
TAG_LABELS = {
    'cpu_percent':       'CPU使用率',
    'mem_metric':        '内存用量',
    'load_average':      '负载均值',
    'net_speed_mb':      '网络速率',
    'net_packets':       '网络包量',
    'disk_util_percent': '磁盘利用率',
    'disk_latency_ms':   '磁盘延迟',
    'disk_rw_sectors':   '磁盘读写',
    'disk_rqm_per_sec':  '磁盘请求',
    'disk_other_metric': '磁盘其他',
    'proc_count':        '进程数',
}

# ── CORS ───────────────────────────────────────────────────
@app.after_request
def add_cors(response):
    response.headers['Access-Control-Allow-Origin'] = '*'
    response.headers['Access-Control-Allow-Headers'] = 'Content-Type'
    response.headers['Access-Control-Allow-Methods'] = 'GET, OPTIONS'
    return response

# ── Helper: run SQL ────────────────────────────────────────
def query(sql, params=None):
    with engine.connect() as conn:
        rows = conn.execute(text(sql), params or {})
        return [dict(row._mapping) for row in rows]

# ── Route: / ────────────────────────────────────────────────
@app.route('/')
def serve_index():
    return send_from_directory(os.path.dirname(os.path.abspath(__file__)), 'index.html')

# ── API: /api/metrics ──────────────────────────────────────
@app.route('/api/metrics', methods=['GET', 'OPTIONS'])
def api_metrics():
    if request.method == 'OPTIONS':
        return '', 204

    hostid = request.args.get('hostid', '').strip()

    # ── 1. Host list + status ──────────────────────────────
    hosts_sql = "SELECT hostid, hostname, model, location1 FROM host_detail ORDER BY hostid"
    hosts = query(hosts_sql)

    # 🔴 Critical / 🟡 Warning based on max disk utilization
    host_status_sql = """
        SELECT d.hostid, MAX(d.value) AS max_disk_util
        FROM disk_tsar d
        WHERE d.tag = 'disk_util_percent'
        GROUP BY d.hostid
    """
    host_disk = query(host_status_sql)
    disk_map = {h['hostid']: h['max_disk_util'] or 0 for h in host_disk}
    ranked = sorted(disk_map.items(), key=lambda x: -x[1])
    critical_host = ranked[0][0] if ranked else None
    warning_hosts = [h for h, _ in ranked[1:3]] if len(ranked) > 2 else []

    host_list = []
    for h in hosts:
        status = 'healthy'
        if h['hostid'] == critical_host:
            status = 'critical'
        elif h['hostid'] in warning_hosts:
            status = 'warning'
        host_list.append({
            'hostid': h['hostid'],
            'hostname': h['hostname'],
            'model': h['model'],
            'location': h['location1'],
            'status': status,
            'max_disk_util': disk_map.get(h['hostid'], 0),
        })

    # ── 2. KPI cards ───────────────────────────────────────
    kpi_sql = """
        SELECT
            COUNT(DISTINCT hostid) AS active_hosts,
            AVG(CASE WHEN tag='cpu_percent' THEN val END) AS avg_cpu,
            SUM(CASE WHEN tag='net_speed_mb' THEN val END) AS total_net
        FROM (
            SELECT hostid, tag, AVG(value) AS val
            FROM pref_tsar
            GROUP BY hostid, tag
        ) t
    """
    kpi_row = query(kpi_sql)
    kpi = {
        'totalHosts': len(hosts),
        'activeHosts': int(kpi_row[0]['active_hosts'] or 0) if kpi_row else 0,
        'avgCpuLoad': round(float(kpi_row[0]['avg_cpu'] or 0), 2) if kpi_row else 0,
        'totalNetThroughput': round(float(kpi_row[0]['total_net'] or 0), 2) if kpi_row else 0,
    }

    # ── 3. Tag distribution ────────────────────────────────
    tag_sql = """
        SELECT tag, SUM(cnt) AS total_count FROM (
            SELECT tag, COUNT(*) AS cnt FROM pref_tsar
            {host_filter} GROUP BY tag
            UNION ALL
            SELECT tag, COUNT(*) AS cnt FROM disk_tsar
            {host_filter} GROUP BY tag
        ) combined
        GROUP BY tag
        ORDER BY total_count DESC
    """
    hf = "WHERE hostid = :hostid" if hostid else ""
    tag_sql = tag_sql.replace("{host_filter}", hf)
    tag_params = {'hostid': hostid} if hostid else {}
    tag_rows = query(tag_sql, tag_params)
    tag_distribution = [
        {'tag': r['tag'], 'label': TAG_LABELS.get(r['tag'], r['tag']), 'count': int(r['total_count'])}
        for r in tag_rows
    ]

    # ── 4. Time series data ────────────────────────────────
    # Pref (CPU, Memory, etc.) and Disk data aggregated by hour
    ts_queries = {
        'cpu_percent': """
            SELECT DATE_FORMAT(FROM_UNIXTIME(ts/1000), '%m-%d %H:00') AS hour_bucket,
                   ROUND(AVG(value),2) AS avg_val, ROUND(MAX(value),2) AS max_val
            FROM pref_tsar WHERE tag='cpu_percent' {host_filter}
            GROUP BY hour_bucket ORDER BY hour_bucket
        """,
        'mem_metric': """
            SELECT DATE_FORMAT(FROM_UNIXTIME(ts/1000), '%m-%d %H:00') AS hour_bucket,
                   ROUND(AVG(value),2) AS avg_val, ROUND(MAX(value),2) AS max_val
            FROM pref_tsar WHERE tag='mem_metric' {host_filter}
            GROUP BY hour_bucket ORDER BY hour_bucket
        """,
        'net_speed_mb': """
            SELECT DATE_FORMAT(FROM_UNIXTIME(ts/1000), '%m-%d %H:00') AS hour_bucket,
                   ROUND(AVG(value),2) AS avg_val, ROUND(MAX(value),2) AS max_val
            FROM pref_tsar WHERE tag='net_speed_mb' {host_filter}
            GROUP BY hour_bucket ORDER BY hour_bucket
        """,
        'disk_latency_ms': """
            SELECT DATE_FORMAT(FROM_UNIXTIME(ts/1000), '%m-%d %H:00') AS hour_bucket,
                   ROUND(AVG(value),2) AS avg_val, ROUND(MAX(value),2) AS max_val
            FROM disk_tsar WHERE tag='disk_latency_ms' {host_filter}
            GROUP BY hour_bucket ORDER BY hour_bucket
        """,
        'disk_util_percent': """
            SELECT DATE_FORMAT(FROM_UNIXTIME(ts/1000), '%m-%d %H:00') AS hour_bucket,
                   ROUND(AVG(value),2) AS avg_val, ROUND(MAX(value),2) AS max_val
            FROM disk_tsar WHERE tag='disk_util_percent' {host_filter}
            GROUP BY hour_bucket ORDER BY hour_bucket
        """,
    }

    time_series = {}
    hf_ts = "AND hostid = :hostid" if hostid else ""
    ts_params = {'hostid': hostid} if hostid else {}

    for tag, sql_tmpl in ts_queries.items():
        sql = sql_tmpl.replace("{host_filter}", hf_ts)
        rows = query(sql, ts_params)
        time_series[tag] = [[r['hour_bucket'], r['avg_val'], r['max_val']] for r in rows]

    # ── 5. Alerts (from max value anomalies) ────────────────
    alert_sql = """
        (SELECT DATE_FORMAT(FROM_UNIXTIME(ts/1000), '%Y-%m-%d %H:%i') AS alert_time,
                hostid, tag, value AS max_value,
                CASE WHEN value >= 99.7 THEN 'critical'
                     WHEN value >= 99.0 THEN 'warning'
                     ELSE 'info' END AS severity
         FROM disk_tsar
         WHERE tag = 'disk_util_percent' AND value >= 99.0
         {host_filter}
        )
        UNION ALL
        (SELECT DATE_FORMAT(FROM_UNIXTIME(ts/1000), '%Y-%m-%d %H:%i') AS alert_time,
                hostid, tag, value AS max_value,
                CASE WHEN value >= 94.8 THEN 'warning'
                     ELSE 'info' END AS severity
         FROM pref_tsar
         WHERE tag = 'cpu_percent' AND value >= 94.0
         {host_filter}
        )
        ORDER BY FIELD(severity,'critical','warning','info'), alert_time DESC
        LIMIT 50
    """
    alert_sql = alert_sql.replace("{host_filter}", hf_ts)
    alert_rows = query(alert_sql, ts_params)
    alerts = [
        {
            'time': r['alert_time'],
            'host': r['hostid'],
            'tag': r['tag'],
            'tagLabel': TAG_LABELS.get(r['tag'], r['tag']),
            'value': round(float(r['max_value']), 2),
            'severity': r['severity'],
        }
        for r in alert_rows
    ]

    kpi['unackedAlerts'] = sum(1 for a in alerts if a['severity'] != 'info')

    # ── Compose response ───────────────────────────────────
    return jsonify({
        'kpi': kpi,
        'hosts': host_list,
        'criticalHost': critical_host,
        'warningHosts': warning_hosts,
        'tagDistribution': tag_distribution,
        'timeSeries': time_series,
        'alerts': alerts,
    })

# ── Run ────────────────────────────────────────────────────
if __name__ == '__main__':
    print("=" * 55)
    print("  TsarPulse — Full-Stack Dashboard")
    print("  http://localhost:5000")
    print("  http://localhost:5000/api/metrics")
    print("  http://localhost:5000/api/metrics?hostid=host010")
    print("=" * 55)
    app.run(debug=True, host='0.0.0.0', port=5000)
