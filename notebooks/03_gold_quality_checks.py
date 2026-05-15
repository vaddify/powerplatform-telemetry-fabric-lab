# Databricks/Fabric notebook source — PySpark
# Notebook: 03_gold_quality_checks
# Lightweight DQ harness. Writes results to pp_gold.dq_results and raises if any check fails.

# %%
from pyspark.sql import functions as F
from datetime import datetime, timezone

GOLD = "pp_gold"
RESULTS_TABLE = f"{GOLD}.dq_results"
run_ts = datetime.now(timezone.utc)

checks = []

def record(name, table, passed, observed, threshold):
    checks.append({
        "run_ts": run_ts,
        "check_name": name,
        "table": table,
        "passed": passed,
        "observed": float(observed) if observed is not None else None,
        "threshold": float(threshold) if threshold is not None else None,
    })

# %%
# ---- Row count > 0 for every fact table ----
for t in ["fact_app_session", "fact_flow_run", "fact_copilot_message"]:
    n = spark.table(f"{GOLD}.{t}").count()
    record(f"row_count_gt_0::{t}", t, n > 0, n, 1)

# ---- Freshness: max(date_key) within last 2 days ----
for t in ["fact_app_session", "fact_flow_run", "fact_copilot_message"]:
    max_dt = spark.table(f"{GOLD}.{t}").agg(F.max("date_key")).first()[0]
    fresh = max_dt is not None and (datetime.now(timezone.utc).date() - max_dt).days <= 2
    record(f"freshness_2d::{t}", t, fresh, None, 2)

# ---- Null environment_id rate < 1% on facts ----
for t in ["fact_app_session", "fact_flow_run", "fact_copilot_message"]:
    df = spark.table(f"{GOLD}.{t}")
    total = df.count() or 1
    nulls = df.where(F.col("environment_id").isNull()).count()
    rate = nulls / total
    record(f"null_env_id_lt_1pct::{t}", t, rate < 0.01, rate, 0.01)

# ---- dim_environment FK coverage on facts ≥ 99% ----
env_ids = {r.environment_id for r in spark.table(f"{GOLD}.dim_environment").select("environment_id").collect()}
env_ids_b = spark.sparkContext.broadcast(env_ids)
for t in ["fact_app_session", "fact_flow_run", "fact_copilot_message"]:
    df = spark.table(f"{GOLD}.{t}")
    total = df.count() or 1
    matched = df.where(F.col("environment_id").isin(list(env_ids_b.value))).count()
    coverage = matched / total
    record(f"env_fk_coverage_ge_99::{t}", t, coverage >= 0.99, coverage, 0.99)

# %%
results_df = spark.createDataFrame(checks)
(results_df.write.format("delta").mode("append").saveAsTable(RESULTS_TABLE))

failed = [c for c in checks if not c["passed"]]
print(f"DQ summary: {len(checks)} checks, {len(failed)} failed")
for f in failed:
    print(f"  FAIL: {f['check_name']} (observed={f['observed']}, threshold={f['threshold']})")

if failed:
    raise Exception(f"{len(failed)} data-quality checks failed; see {RESULTS_TABLE}")
