"""Export dashboard KPI data from telemetry.db to JSON.

Queries synthetic telemetry data and generates a JSON file for the
GitHub Pages KPI Metrics Dashboard. All data is synthetic — for demo only.

Output: docs/pages/assets/dashboard-data.json
"""

import json
import sqlite3
from datetime import datetime, timezone
from pathlib import Path


def connect_db() -> sqlite3.Connection:
    """Connect to the telemetry database."""
    db_path = Path(__file__).parent.parent / "data" / "telemetry.db"
    conn = sqlite3.connect(str(db_path))
    conn.row_factory = sqlite3.Row
    return conn


def query_gpu_avg_by_cluster(conn: sqlite3.Connection) -> list[dict]:
    """Average GPU utilization and memory by cluster (all-time)."""
    query = """
        SELECT cluster,
               ROUND(AVG(utilization_pct), 2) as avg_util,
               ROUND(MAX(utilization_pct), 2) as max_util,
               ROUND(MIN(utilization_pct), 2) as min_util,
               ROUND(AVG(mem_pct), 2) as avg_mem
        FROM telemetry_gpu
        GROUP BY cluster
        ORDER BY cluster
    """
    return [dict(row) for row in conn.execute(query).fetchall()]


def query_gpu_daily_trend(conn: sqlite3.Connection) -> list[dict]:
    """Daily GPU utilization trend by cluster."""
    query = """
        SELECT DATE(ts) as date,
               cluster,
               ROUND(AVG(utilization_pct), 2) as avg_util
        FROM telemetry_gpu
        GROUP BY DATE(ts), cluster
        ORDER BY date, cluster
    """
    return [dict(row) for row in conn.execute(query).fetchall()]


def query_gpu_anomalies(conn: sqlite3.Connection) -> list[dict]:
    """GPU anomalies: daily avg below 30% or above 95% by cluster/node."""
    query = """
        SELECT DATE(ts) as date,
               cluster,
               node,
               ROUND(AVG(utilization_pct), 2) as avg_util
        FROM telemetry_gpu
        GROUP BY DATE(ts), cluster, node
        HAVING avg_util < 30 OR avg_util > 95
        ORDER BY date, cluster, node
    """
    return [dict(row) for row in conn.execute(query).fetchall()]


def query_net_latency_by_site(conn: sqlite3.Connection) -> list[dict]:
    """Network latency stats by site (all-time).

    SQLite lacks PERCENTILE_CONT, so percentiles are computed manually.
    """
    query_simple = """
        SELECT site,
               ROUND(AVG(latency_ms), 2) as avg_latency,
               ROUND(AVG(loss_pct), 2) as avg_loss
        FROM telemetry_net
        GROUP BY site
        ORDER BY site
    """
    rows = conn.execute(query_simple).fetchall()
    
    # Calculate percentiles manually
    result = []
    for row in rows:
        site = row[0]
        # Get sorted latencies for this site
        latencies = [r[0] for r in conn.execute(
            "SELECT latency_ms FROM telemetry_net WHERE site = ? ORDER BY latency_ms",
            (site,)
        ).fetchall()]
        
        p95_idx = int(len(latencies) * 0.95)
        p99_idx = int(len(latencies) * 0.99)
        
        result.append({
            "site": site,
            "avg_latency": row[1],
            "p95_latency": round(latencies[p95_idx] if latencies else 0, 2),
            "p99_latency": round(latencies[p99_idx] if latencies else 0, 2),
            "avg_loss": row[2]
        })
    
    return result


def query_net_daily_trend(conn: sqlite3.Connection) -> list[dict]:
    """Daily network latency and throughput trend by site."""
    query = """
        SELECT DATE(ts) as date,
               site,
               ROUND(AVG(latency_ms), 2) as avg_latency,
               ROUND(AVG(throughput_gbps), 2) as avg_throughput
        FROM telemetry_net
        GROUP BY DATE(ts), site
        ORDER BY date, site
    """
    return [dict(row) for row in conn.execute(query).fetchall()]


def query_net_anomalies(conn: sqlite3.Connection) -> list[dict]:
    """Network anomalies: daily max latency > 100ms or max loss > 5%."""
    query = """
        SELECT DATE(ts) as date,
               site,
               ROUND(MAX(latency_ms), 2) as max_latency,
               ROUND(MAX(loss_pct), 2) as max_loss
        FROM telemetry_net
        GROUP BY DATE(ts), site
        HAVING max_latency > 100 OR max_loss > 5
        ORDER BY date, site
    """
    return [dict(row) for row in conn.execute(query).fetchall()]


def query_cost_total_by_cluster(conn: sqlite3.Connection) -> list[dict]:
    """Total cost and token cost by cluster (all-time)."""
    query = """
        SELECT cluster,
               ROUND(SUM(cost_usd), 2) as total_cost,
               ROUND(SUM(token_cost_usd), 2) as total_token_cost
        FROM telemetry_cost
        GROUP BY cluster
        ORDER BY cluster
    """
    return [dict(row) for row in conn.execute(query).fetchall()]


def query_cost_daily_trend(conn: sqlite3.Connection) -> list[dict]:
    """Daily cost trend by cluster."""
    query = """
        SELECT DATE(ts) as date,
               cluster,
               ROUND(SUM(cost_usd), 2) as daily_cost,
               ROUND(SUM(token_cost_usd), 2) as daily_token_cost
        FROM telemetry_cost
        GROUP BY DATE(ts), cluster
        ORDER BY date, cluster
    """
    return [dict(row) for row in conn.execute(query).fetchall()]


def query_cost_anomalies(conn: sqlite3.Connection) -> list[dict]:
    """Cost anomalies: daily cost exceeds 2x cluster's overall daily average."""
    # First, calculate the baseline average daily cost per cluster
    baseline_query = """
        SELECT cluster,
               AVG(daily_cost) as baseline_avg
        FROM (
            SELECT cluster,
                   DATE(ts) as date,
                   SUM(cost_usd) as daily_cost
            FROM telemetry_cost
            GROUP BY cluster, DATE(ts)
        )
        GROUP BY cluster
    """
    baselines = {row[0]: row[1] for row in conn.execute(baseline_query).fetchall()}
    
    # Find anomalies
    daily_query = """
        SELECT DATE(ts) as date,
               cluster,
               ROUND(SUM(cost_usd), 2) as daily_cost
        FROM telemetry_cost
        GROUP BY DATE(ts), cluster
        ORDER BY date, cluster
    """
    
    anomalies = []
    for row in conn.execute(daily_query).fetchall():
        date, cluster, daily_cost = row[0], row[1], row[2]
        baseline_avg = baselines.get(cluster, 0)
        if daily_cost > 2 * baseline_avg:
            anomalies.append({
                "date": date,
                "cluster": cluster,
                "daily_cost": daily_cost,
                "baseline_avg": round(baseline_avg, 2)
            })
    
    return anomalies


def query_incidents_summary(conn: sqlite3.Connection) -> list[dict]:
    """Incident summary by severity and status."""
    query = """
        SELECT severity,
               SUM(CASE WHEN status = 'open' THEN 1 ELSE 0 END) as open,
               SUM(CASE WHEN status = 'resolved' THEN 1 ELSE 0 END) as resolved,
               SUM(CASE WHEN status = 'investigating' THEN 1 ELSE 0 END) as investigating
        FROM incidents
        GROUP BY severity
        ORDER BY severity
    """
    return [dict(row) for row in conn.execute(query).fetchall()]


def query_incidents_list(conn: sqlite3.Connection) -> list[dict]:
    """Recent incidents list (last 30 days, limit 50)."""
    query = """
        SELECT ts, service, symptom, severity, status
        FROM incidents
        ORDER BY ts DESC
        LIMIT 50
    """
    return [dict(row) for row in conn.execute(query).fetchall()]


def calculate_mttr(conn: sqlite3.Connection) -> float:
    """Calculate Mean Time to Resolve (MTTR) in hours.
    
    For resolved incidents, estimate resolution time as 4-24 hours (synthetic).
    """
    query = """
        SELECT COUNT(*) as resolved_count
        FROM incidents
        WHERE status = 'resolved'
    """
    count = conn.execute(query).fetchone()[0]
    
    # Synthetic MTTR calculation (we don't have actual resolution timestamps)
    # Use a reasonable estimate for demo: avg 12 hours
    if count == 0:
        return 0.0
    
    return 12.0  # Placeholder for synthetic data


def calculate_health_scores(
    gpu_data: list[dict],
    net_data: list[dict],
    cost_anomalies: list[dict],
    incidents_summary: list[dict]
) -> dict:
    """Calculate infrastructure health scores.
    
    GPU: 1.0 if avg 40-80%, degrade outside
    Network: 1.0 if avg latency <30ms and loss <1%
    Cost: 1.0 if no anomalies, 0.5 if anomalies
    Incidents: 1.0 if no open, degrade by severity (P1=-0.3, P2=-0.2, P3=-0.1)
    Overall: weighted average (GPU 30%, Net 25%, Cost 20%, Inc 25%)
    """
    # GPU score
    if gpu_data:
        avg_util = sum(row["avg_util"] for row in gpu_data) / len(gpu_data)
        if 40 <= avg_util <= 80:
            gpu_score = 1.0
        elif avg_util < 40:
            gpu_score = max(0.0, avg_util / 40)
        else:  # > 80
            gpu_score = max(0.0, 1.0 - (avg_util - 80) / 20)
    else:
        gpu_score = 0.0
    
    # Network score
    if net_data:
        avg_latency = sum(row["avg_latency"] for row in net_data) / len(net_data)
        avg_loss = sum(row["avg_loss"] for row in net_data) / len(net_data)
        
        latency_score = 1.0 if avg_latency < 30 else max(0.0, 1.0 - (avg_latency - 30) / 100)
        loss_score = 1.0 if avg_loss < 1 else max(0.0, 1.0 - (avg_loss - 1) / 10)
        net_score = (latency_score + loss_score) / 2
    else:
        net_score = 0.0
    
    # Cost score
    cost_score = 0.5 if cost_anomalies else 1.0
    
    # Incidents score
    incidents_score = 1.0
    for row in incidents_summary:
        severity = row["severity"]
        open_count = row["open"]
        investigating_count = row["investigating"]
        
        if severity == "P1":
            incidents_score -= (open_count + investigating_count) * 0.3
        elif severity == "P2":
            incidents_score -= (open_count + investigating_count) * 0.2
        elif severity == "P3":
            incidents_score -= (open_count + investigating_count) * 0.1
    
    incidents_score = max(0.0, min(1.0, incidents_score))
    
    # Overall weighted score
    overall_score = (
        gpu_score * 0.30 +
        net_score * 0.25 +
        cost_score * 0.20 +
        incidents_score * 0.25
    )
    
    return {
        "overall": round(overall_score, 2),
        "components": {
            "gpu": round(gpu_score, 2),
            "network": round(net_score, 2),
            "cost": round(cost_score, 2),
            "incidents": round(incidents_score, 2)
        }
    }


def export_dashboard_data() -> dict:
    """Export all dashboard data to structured JSON."""
    conn = connect_db()
    
    # GPU queries
    gpu_avg_by_cluster = query_gpu_avg_by_cluster(conn)
    gpu_daily_trend = query_gpu_daily_trend(conn)
    gpu_anomalies = query_gpu_anomalies(conn)
    
    # Network queries
    net_latency_by_site = query_net_latency_by_site(conn)
    net_daily_trend = query_net_daily_trend(conn)
    net_anomalies = query_net_anomalies(conn)
    
    # Cost queries
    cost_total_by_cluster = query_cost_total_by_cluster(conn)
    cost_daily_trend = query_cost_daily_trend(conn)
    cost_anomalies = query_cost_anomalies(conn)
    
    # Incidents queries
    incidents_summary = query_incidents_summary(conn)
    incidents_list = query_incidents_list(conn)
    mttr_hours = calculate_mttr(conn)
    
    # Health scores
    health_scores = calculate_health_scores(
        gpu_avg_by_cluster,
        net_latency_by_site,
        cost_anomalies,
        incidents_summary
    )
    
    conn.close()
    
    # Build JSON structure
    data = {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "disclaimer": "All data is synthetic — for demo purposes only.",
        "gpu": {
            "avg_by_cluster": gpu_avg_by_cluster,
            "daily_trend": gpu_daily_trend,
            "anomalies": gpu_anomalies
        },
        "network": {
            "latency_by_site": net_latency_by_site,
            "daily_trend": net_daily_trend,
            "anomalies": net_anomalies
        },
        "cost": {
            "total_by_cluster": cost_total_by_cluster,
            "daily_trend": cost_daily_trend,
            "anomalies": cost_anomalies
        },
        "incidents": {
            "summary": incidents_summary,
            "list": incidents_list,
            "mttr_hours": mttr_hours
        },
        "health_score": health_scores,
        "kpi_questions": [
            {
                "category": "GPU",
                "question": "What is my average GPU utilization across clusters?",
                "insight": "Are we over/under-provisioned?"
            },
            {
                "category": "GPU",
                "question": "Which nodes are running hot (>85%) or cold (<30%)?",
                "insight": "Spot waste or capacity risk"
            },
            {
                "category": "GPU",
                "question": "When did GPU utilization anomalies occur?",
                "insight": "Timeline view with anomaly markers"
            },
            {
                "category": "Network",
                "question": "What is my P50/P95/P99 network latency by site?",
                "insight": "SLA compliance check"
            },
            {
                "category": "Network",
                "question": "Which sites have elevated packet loss?",
                "insight": "Identify degraded links"
            },
            {
                "category": "Network",
                "question": "What is my throughput trend?",
                "insight": "Capacity planning signal"
            },
            {
                "category": "Cost",
                "question": "What is my total spend by cluster?",
                "insight": "Budget allocation view"
            },
            {
                "category": "Cost",
                "question": "Are there cost spikes vs. the baseline?",
                "insight": "Anomaly detection for FinOps"
            },
            {
                "category": "Cost",
                "question": "What is my cost per GPU-hour?",
                "insight": "Efficiency KPI"
            },
            {
                "category": "Cost",
                "question": "How do token costs compare to compute costs?",
                "insight": "AI workload cost breakdown"
            },
            {
                "category": "Incidents",
                "question": "What is my Mean Time to Resolve (MTTR)?",
                "insight": "Operational maturity signal"
            },
            {
                "category": "Incidents",
                "question": "How many open vs. resolved incidents by severity?",
                "insight": "Current risk posture"
            },
            {
                "category": "Incidents",
                "question": "Are incidents correlated with recent changes?",
                "insight": "Change-failure rate proxy"
            },
            {
                "category": "Composite",
                "question": "What is my overall infrastructure health score?",
                "insight": "Weighted composite"
            },
            {
                "category": "Composite",
                "question": "What is the change-failure correlation rate?",
                "insight": "Incidents within 24h of a change event"
            }
        ]
    }
    
    return data


def main():
    """Main entry point."""
    # Ensure output directory exists
    output_dir = Path(__file__).parent.parent / "docs" / "pages" / "assets"
    output_dir.mkdir(parents=True, exist_ok=True)
    
    # Export data
    print("Exporting dashboard data from telemetry.db...")
    data = export_dashboard_data()
    
    # Write JSON
    output_file = output_dir / "dashboard-data.json"
    with open(output_file, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=2)
    
    print(f"✅ Dashboard data exported to: {output_file}")
    print("\n📊 Summary:")
    print(f"   - GPU clusters: {len(data['gpu']['avg_by_cluster'])}")
    print(f"   - GPU anomalies: {len(data['gpu']['anomalies'])}")
    print(f"   - Network sites: {len(data['network']['latency_by_site'])}")
    print(f"   - Network anomalies: {len(data['network']['anomalies'])}")
    print(f"   - Cost anomalies: {len(data['cost']['anomalies'])}")
    print(f"   - Incidents: {len(data['incidents']['list'])}")
    print(f"   - MTTR: {data['incidents']['mttr_hours']} hours")
    print(f"   - Overall health score: {data['health_score']['overall']}")
    print("\n🏥 Component health scores:")
    for component, score in data['health_score']['components'].items():
        print(f"   - {component.capitalize()}: {score}")


if __name__ == "__main__":
    main()
