# Fabric notebooks — pp_bronze → pp_silver → pp_gold

These are **PySpark** notebooks formatted as `# %%` cell-delimited `.py` files for clean diffs in source control. To use them in Fabric:

1. Open the workspace → **+ New** → **Notebook**.
2. Click the `...` menu → **Import** → **Upload from local** → select the `.py` file.
3. Fabric converts `# %%` markers to cells.

Alternatively in VS Code: install the **Jupyter** extension and these files open natively as notebooks.

| File | Source → Sink | Schedule |
|---|---|---|
| [01_bronze_to_silver.py](./01_bronze_to_silver.py) | `pp_bronze.events_raw` → `pp_silver.{app_telemetry, flow_runs, copilot_messages, dataverse_events, tenant_metrics}` | 30 min |
| [02_silver_to_gold.py](./02_silver_to_gold.py) | `pp_silver.*` → `pp_gold.{dim_*, fact_*}` | 1 h |
| [03_gold_quality_checks.py](./03_gold_quality_checks.py) | `pp_gold.*` → `pp_gold.dq_results` (alerts on fail) | 1 h |

[measures.dax](./measures.dax) — seed Power BI measures for the Direct Lake semantic model on `pp_gold`.

Wire these into a **Data Factory pipeline** with **Notebook activity** + **On failure** branches that post to a Teams webhook.
