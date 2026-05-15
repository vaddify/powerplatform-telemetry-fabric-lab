# Databricks/Fabric notebook source — PySpark
# Notebook: 02_silver_to_gold
# Builds star-schema dim/fact tables in pp_gold for Direct Lake consumption.

# %%
from pyspark.sql import functions as F
from pyspark.sql.window import Window

GOLD = "pp_gold"
spark.sql(f"CREATE SCHEMA IF NOT EXISTS {GOLD}")

# %%
# -------- dim_date (regenerate fully each run; cheap) --------
date_df = (
    spark.sql("SELECT explode(sequence(to_date('2024-01-01'), to_date('2027-12-31'), interval 1 day)) AS date_key")
    .withColumn("year", F.year("date_key"))
    .withColumn("quarter", F.quarter("date_key"))
    .withColumn("month", F.month("date_key"))
    .withColumn("month_name", F.date_format("date_key", "MMMM"))
    .withColumn("day", F.dayofmonth("date_key"))
    .withColumn("day_of_week", F.dayofweek("date_key"))
    .withColumn("is_weekend", F.dayofweek("date_key").isin(1, 7))
)
date_df.write.format("delta").mode("overwrite").saveAsTable(f"{GOLD}.dim_date")

# %%
# -------- dim_environment --------
# Prefer Dataverse mirror (CoE Kit) if available; fall back to BAP API data.
DV_ENV = "pp_silver.dv_environments"
if spark.catalog.tableExists(DV_ENV):
    env_df = spark.read.table(DV_ENV).select(
        "environment_id", "environment_name", "sku", "region",
        F.col("env_type").alias("environment_type"),
        "created_date",
        "maker_count", "app_count", "flow_count",
    ).dropDuplicates(["environment_id"])
else:
    # Fallback: parse from BAP tenant_metrics (less rich)
    env_df = spark.read.table("pp_silver.tenant_metrics") \
        .where(F.col("eventType") == "pp.tenant.environments") \
        .select(F.from_json("payload_json",
            "STRUCT<value:ARRAY<STRUCT<id:STRING,name:STRING,location:STRING,sku:STRING,createdTime:TIMESTAMP>>>").alias("p")) \
        .select(F.explode("p.value").alias("e")) \
        .select(
            F.col("e.id").alias("environment_id"),
            F.col("e.name").alias("environment_name"),
            F.col("e.location").alias("region"),
            F.col("e.sku").alias("sku"),
            F.col("e.createdTime").alias("created_date"),
        ).dropDuplicates(["environment_id"])

env_df.write.format("delta").mode("overwrite").saveAsTable(f"{GOLD}.dim_environment")

# %%
# -------- dim_app --------
# Prefer Dataverse mirror (CoE Kit) if available; fall back to telemetry stream.
DV_APPS = "pp_silver.dv_apps"
if spark.catalog.tableExists(DV_APPS):
    app_df = spark.read.table(DV_APPS).select(
        "app_id", "app_name", "app_type",
        F.col("owner_id").alias("maker_id"),
        F.col("owner_name").alias("maker_name"),
        "environment_id", "connectors",
        "created_date", "modified_date",
        "shared_user_count", "last_launched_date",
    ).dropDuplicates(["app_id"])
else:
    # Fallback: latest-seen from telemetry
    w = Window.partitionBy("app_id").orderBy(F.col("eventTime").desc())
    app_df = (
        spark.read.table("pp_silver.app_telemetry")
        .withColumn("rn", F.row_number().over(w))
        .where("rn = 1")
        .select("app_id", "app_name", "maker_id", "environment_id")
    )

app_df.write.format("delta").mode("overwrite").saveAsTable(f"{GOLD}.dim_app")

# %%
# -------- dim_maker (from Dataverse mirror) --------
DV_MAKERS = "pp_silver.dv_makers"
if spark.catalog.tableExists(DV_MAKERS):
    maker_df = spark.read.table(DV_MAKERS).select(
        "maker_id", "display_name", "upn",
        "city", "country", "department",
        "first_time_maker",
    ).dropDuplicates(["maker_id"])
    maker_df.write.format("delta").mode("overwrite").saveAsTable(f"{GOLD}.dim_maker")
    print(f"✓ dim_maker: {maker_df.count()} rows")
else:
    print("⚠ dim_maker skipped — dv_makers not available (enable Link to Fabric)")

# %%
# -------- dim_connector (from Dataverse mirror) --------
DV_CONN = "pp_silver.dv_connectors"
if spark.catalog.tableExists(DV_CONN):
    conn_df = spark.read.table(DV_CONN).select(
        "connector_id", "connector_name", "tier", "publisher",
    ).dropDuplicates(["connector_id"])
    conn_df.write.format("delta").mode("overwrite").saveAsTable(f"{GOLD}.dim_connector")
    print(f"✓ dim_connector: {conn_df.count()} rows")
else:
    print("⚠ dim_connector skipped — dv_connectors not available")

# %%
# -------- dim_dlp_policy (from Dataverse mirror) --------
DV_DLP = "pp_silver.dv_dlp_policies"
if spark.catalog.tableExists(DV_DLP):
    dlp_df = spark.read.table(DV_DLP).select(
        "policy_id", "policy_name", "scope", "environment_count",
        "connectors_business", "connectors_nondata", "connectors_blocked",
    ).dropDuplicates(["policy_id"])
    dlp_df.write.format("delta").mode("overwrite").saveAsTable(f"{GOLD}.dim_dlp_policy")
    print(f"✓ dim_dlp_policy: {dlp_df.count()} rows")
else:
    print("⚠ dim_dlp_policy skipped — dv_dlp_policies not available")

# %%
# -------- fact_app_launch (MAU source from Dataverse mirror) --------
DV_LAUNCHES = "pp_silver.dv_app_launches"
if spark.catalog.tableExists(DV_LAUNCHES):
    launches = (
        spark.read.table(DV_LAUNCHES)
        .withColumn("date_key", F.to_date("launch_date"))
        .select("launch_id", "date_key", "app_id", "user_id")
    )
    (launches.write.format("delta")
        .mode("overwrite")
        .partitionBy("date_key")
        .saveAsTable(f"{GOLD}.fact_app_launch"))
    print(f"✓ fact_app_launch: {launches.count()} rows")
else:
    print("⚠ fact_app_launch skipped — dv_app_launches not available")

# %%
# -------- fact_app_session --------
sess = (
    spark.read.table("pp_silver.app_telemetry")
    .withColumn("date_key", F.to_date("eventTime"))
    .select("session_id", "date_key", "app_id", "environment_id", "duration_ms", "error_count", "device_type")
)
(sess.write.format("delta")
    .mode("overwrite")
    .partitionBy("date_key")
    .saveAsTable(f"{GOLD}.fact_app_session"))

# %%
# -------- fact_flow_run --------
runs = (
    spark.read.table("pp_silver.flow_runs")
    .withColumn("date_key", F.to_date("start_time"))
    .select("run_id", "date_key", "flow_id", "environment_id", "status", "duration_seconds", "trigger_type")
)
(runs.write.format("delta")
    .mode("overwrite")
    .partitionBy("date_key")
    .saveAsTable(f"{GOLD}.fact_flow_run"))

# %%
# -------- fact_copilot_message --------
msgs = (
    spark.read.table("pp_silver.copilot_messages")
    .withColumn("date_key", F.to_date("eventTime"))
    .select("conversation_id", "date_key", "agent_id", "environment_id", "role", "tokens_in", "tokens_out", "intent", "escalated")
)
(msgs.write.format("delta")
    .mode("overwrite")
    .partitionBy("date_key")
    .saveAsTable(f"{GOLD}.fact_copilot_message"))

# %%
# Optimize for Direct Lake (V-Order on by default in Fabric runtime)
gold_tables = [
    "dim_date", "dim_environment", "dim_app",
    "dim_maker", "dim_connector", "dim_dlp_policy",
    "fact_app_session", "fact_flow_run", "fact_copilot_message", "fact_app_launch",
]
for t in gold_tables:
    full = f"{GOLD}.{t}"
    if spark.catalog.tableExists(full):
        spark.sql(f"OPTIMIZE {full}")
        print(f"✓ Optimized {full}")
    else:
        print(f"⚠ Skipped {full} (not created)")

print("\nSilver → Gold complete.")
