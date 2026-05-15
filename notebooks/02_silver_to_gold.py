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
# -------- dim_environment (SCD-1 from Dataverse mirror) --------
# If using "Link to Microsoft Fabric" the table is admin_environment in the mirrored lakehouse.
# Adjust the source name to match your workspace.
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
        F.col("e.createdTime").alias("created_time"),
    ).dropDuplicates(["environment_id"])

env_df.write.format("delta").mode("overwrite").saveAsTable(f"{GOLD}.dim_environment")

# %%
# -------- dim_app (latest seen name per app) --------
w = Window.partitionBy("app_id").orderBy(F.col("eventTime").desc())
app_df = (
    spark.read.table("pp_silver.app_telemetry")
    .withColumn("rn", F.row_number().over(w))
    .where("rn = 1")
    .select("app_id", "app_name", "maker_id", "environment_id")
)
app_df.write.format("delta").mode("overwrite").saveAsTable(f"{GOLD}.dim_app")

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
for t in ["dim_date", "dim_environment", "dim_app", "fact_app_session", "fact_flow_run", "fact_copilot_message"]:
    spark.sql(f"OPTIMIZE {GOLD}.{t}")

print("Silver → Gold complete.")
