# Azure Monitor Workbook — Agentic Ops Advisor

This directory contains the Azure Monitor Workbook template for monitoring the
**Agentic Ops Advisor** agent in production.

## Panels

| # | Panel | Data Source | KQL Table |
|---|-------|-------------|-----------|
| 1 | **Request Count / Throughput** | Agent invocations per 5 min and hourly summary | `requests` |
| 2 | **Latency (P50 / P95 / P99)** | Response time percentiles over time | `requests` |
| 3 | **Tool Failure Rate** | % of tool calls that failed, by tool name | `dependencies` |
| 4 | **Quality Score Trend** | Eval scores (groundedness, relevance, tool_accuracy, safety) over time | `customMetrics`, `traces` |

## Prerequisites

- An **Azure Application Insights** resource with telemetry from the agent
- The agent must emit traces to App Insights (set `APPLICATIONINSIGHTS_CONNECTION_STRING` in `.env`)
- Quality scores must be logged as `customMetrics` by the eval runner (see `eval/run_eval.py`)

## Import Instructions

### Option A — Azure Portal (recommended)

1. Open the [Azure Portal](https://portal.azure.com)
2. Navigate to **Monitor** → **Workbooks**
3. Click **+ New** (top-left toolbar)
4. Click the **`</>`** (Advanced Editor) button in the top toolbar
5. Replace the entire content with the contents of `monitoring/workbook.json`
6. Click **Apply**
7. In the **App Insights Resource** parameter dropdown, select your Application Insights resource
8. Adjust the **Time Range** as needed
9. Click **Save** (💾) to persist the workbook to your Azure subscription

### Option B — Azure CLI (ARM template deployment)

You can wrap `workbook.json` in an ARM template resource and deploy via CLI.

```bash
# Example: deploy the workbook as an ARM resource
az deployment group create \
  --resource-group rg-agentic-ops-advisor \
  --template-file infra/workbook-arm.json \
  --parameters appInsightsId="/subscriptions/<sub>/resourceGroups/rg-agentic-ops-advisor/providers/microsoft.insights/components/<name>"
```

### Option C — Bicep (infrastructure as code)

Reference the workbook JSON from your Bicep template:

```bicep
resource agentWorkbook 'Microsoft.Insights/workbooks@2022-04-01' = {
  name: guid(resourceGroup().id, 'agentic-ops-workbook')
  location: location
  kind: 'shared'
  properties: {
    displayName: 'Agentic Ops Advisor'
    serializedData: loadTextContent('../monitoring/workbook.json')
    sourceId: appInsights.id
    category: 'workbook'
  }
}
```

## Parameters

| Parameter | Type | Description |
|-----------|------|-------------|
| `TimeRange` | Time range picker | Filters all panels (default: last 24 h). Pre-set options: 30 min, 1 h, 4 h, 12 h, 24 h, 3 d, 7 d, 30 d |
| `AppInsightsResource` | Resource picker | The Application Insights resource to query. **Must be set** before any panel renders data |

## KQL Query Notes

### Throughput panel
```kql
requests
| where timestamp {TimeRange}
| where name has 'agent' or name has 'invoke'
    or name has 'chat' or cloud_RoleName has 'agentic'
| summarize Invocations = count() by bin(timestamp, 5m)
| order by timestamp asc
```
Adjust the `name`/`cloud_RoleName` filter to match your deployment's request naming convention.

### Latency panel
```kql
requests
| where timestamp {TimeRange}
| where name has 'agent' or name has 'invoke'
    or name has 'chat' or cloud_RoleName has 'agentic'
| summarize
    P50 = percentile(duration, 50),
    P95 = percentile(duration, 95),
    P99 = percentile(duration, 99)
  by bin(timestamp, 15m)
| order by timestamp asc
```

### Tool Failure Rate panel
```kql
dependencies
| where timestamp {TimeRange}
| where type in ('Function', 'SQL', 'HTTP')
    or name has 'tool'
    or name has 'query_telemetry'
    or name has 'propose_action'
    or name has 'get_work_context'
| summarize
    TotalCalls  = count(),
    FailedCalls = countif(success == false),
    FailureRate = round(100.0 * countif(success == false) / count(), 1)
  by ToolName = name
| order by FailureRate desc
```

### Quality Score Trend panel
```kql
customMetrics
| where timestamp {TimeRange}
| where name in (
    'eval.groundedness',
    'eval.relevance',
    'eval.tool_accuracy',
    'eval.safety'
  )
| summarize AvgScore = round(avg(value), 2)
  by bin(timestamp, 1h), EvaluatorName = name
| order by timestamp asc
```

For this panel to populate, the eval runner must emit metrics via OpenTelemetry:

```python
from opentelemetry import metrics
meter = metrics.get_meter("agentic-ops-advisor.eval")
score_gauge = meter.create_gauge("eval.groundedness")
score_gauge.set(score_value, {"eval_name": "groundedness"})
```

## Customization Tips

- **Change bin size**: Replace `bin(timestamp, 5m)` with `1m`, `15m`, `1h`, etc.
- **Add new tools**: Extend the `name has '...'` filter in the Tool Failure Rate query.
- **Add a new evaluator**: Add its metric name to the `where name in (...)` list.
- **Export as PNG**: Use the **Download** (📥) menu on any tile → *Download as image*.
- **Pin to Dashboard**: Click the 📌 icon on any tile to pin it to your Azure Dashboard.

## Troubleshooting

| Symptom | Fix |
|---------|-----|
| All panels show "No data" | Check that `AppInsightsResource` parameter is set and that the agent is emitting telemetry |
| Latency panels empty | The agent requests must include the `cloud_RoleName` or a name matching the filter |
| Quality Score panel empty | Ensure eval runner logs `customMetrics` with names like `eval.groundedness` |
| Import fails with "invalid JSON" | Make sure you copied the full file content including opening/closing braces |
