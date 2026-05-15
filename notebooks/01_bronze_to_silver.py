# Databricks/Fabric notebook source — PySpark
# Notebook: 01_bronze_to_silver
# Reads raw JSON envelopes from pp_bronze.events_raw and writes typed Delta tables
# into pp_silver, partitioned by event date, with idempotent merges.

# %%
from pyspark.sql import functions as F
from pyspark.sql.types import StructType, StructField, StringType, TimestampType, MapType
from delta.tables import DeltaTable

BRONZE = "pp_bronze.events_raw"
SILVER_DB = "pp_silver"

spark.sql(f"CREATE SCHEMA IF NOT EXISTS {SILVER_DB}")

# %%
# Bronze layout (from Eventstream): one row per Event Hub message.
#   body          : string  (JSON envelope from forwarder or diagnostic settings)
#   enqueuedTime  : timestamp
#   partition     : string
raw = (
    spark.read.format("delta").table(BRONZE)
    .where(F.col("enqueuedTime") >= F.current_timestamp() - F.expr("INTERVAL 2 HOURS"))
)

# %%
parsed = (
    raw
    .withColumn("envelope", F.from_json(F.col("body"), "STRUCT<eventType:STRING, timestamp:TIMESTAMP, data:STRING>"))
    .select(
        F.col("envelope.eventType").alias("eventType"),
        F.col("envelope.timestamp").alias("eventTime"),
        F.col("envelope.data").alias("data_json"),
        F.col("enqueuedTime"),
    )
    .where(F.col("eventType").isNotNull())
)

parsed.cache()

# %%
def upsert(df, table, keys):
    """Idempotent merge into a Delta table partitioned by event_date."""
    full = f"{SILVER_DB}.{table}"
    df = df.withColumn("event_date", F.to_date("eventTime"))
    if not spark.catalog.tableExists(full):
        (df.write.format("delta")
            .partitionBy("event_date")
            .mode("overwrite")
            .saveAsTable(full))
        return
    target = DeltaTable.forName(spark, full)
    cond = " AND ".join([f"t.{k} = s.{k}" for k in keys])
    (target.alias("t")
        .merge(df.alias("s"), cond)
        .whenMatchedUpdateAll()
        .whenNotMatchedInsertAll()
        .execute())

# %%
# --- Power Apps telemetry (from Application Insights / diagnostic settings) ---
app_schema = "STRUCT<sessionId:STRING, appId:STRING, appName:STRING, makerId:STRING, environmentId:STRING, durationMs:LONG, errors:LONG, deviceType:STRING>"
app_df = (
    parsed.where(F.col("eventType") == "pp.powerapps.session")
    .withColumn("d", F.from_json("data_json", app_schema))
    .select(
        "eventTime",
        F.col("d.sessionId").alias("session_id"),
        F.col("d.appId").alias("app_id"),
        F.col("d.appName").alias("app_name"),
        F.col("d.makerId").alias("maker_id"),
        F.col("d.environmentId").alias("environment_id"),
        F.col("d.durationMs").cast("long").alias("duration_ms"),
        F.col("d.errors").cast("int").alias("error_count"),
        F.col("d.deviceType").alias("device_type"),
    )
)
upsert(app_df, "app_telemetry", ["session_id"])

# %%
# --- Power Automate flow runs ---
flow_schema = "STRUCT<runId:STRING, flowId:STRING, flowName:STRING, environmentId:STRING, status:STRING, startTime:TIMESTAMP, endTime:TIMESTAMP, triggerType:STRING>"
flow_df = (
    parsed.where(F.col("eventType") == "pp.powerautomate.run")
    .withColumn("d", F.from_json("data_json", flow_schema))
    .select(
        "eventTime",
        F.col("d.runId").alias("run_id"),
        F.col("d.flowId").alias("flow_id"),
        F.col("d.flowName").alias("flow_name"),
        F.col("d.environmentId").alias("environment_id"),
        F.col("d.status").alias("status"),
        F.col("d.startTime").alias("start_time"),
        F.col("d.endTime").alias("end_time"),
        F.col("d.triggerType").alias("trigger_type"),
        (F.unix_timestamp("d.endTime") - F.unix_timestamp("d.startTime")).alias("duration_seconds"),
    )
)
upsert(flow_df, "flow_runs", ["run_id"])

# %%
# --- Copilot Studio messages ---
copilot_schema = "STRUCT<conversationId:STRING, agentId:STRING, environmentId:STRING, role:STRING, tokensIn:LONG, tokensOut:LONG, intent:STRING, escalated:BOOLEAN>"
copilot_df = (
    parsed.where(F.col("eventType") == "pp.copilotstudio.message")
    .withColumn("d", F.from_json("data_json", copilot_schema))
    .select(
        "eventTime",
        F.col("d.conversationId").alias("conversation_id"),
        F.col("d.agentId").alias("agent_id"),
        F.col("d.environmentId").alias("environment_id"),
        F.col("d.role").alias("role"),
        F.col("d.tokensIn").cast("long").alias("tokens_in"),
        F.col("d.tokensOut").cast("long").alias("tokens_out"),
        F.col("d.intent").alias("intent"),
        F.col("d.escalated").cast("boolean").alias("escalated"),
    )
)
upsert(copilot_df, "copilot_messages", ["conversation_id", "eventTime"])

# %%
# --- Dataverse audit / plug-in events ---
dv_schema = "STRUCT<entity:STRING, operation:STRING, userId:STRING, environmentId:STRING, recordId:STRING, durationMs:LONG, success:BOOLEAN>"
dv_df = (
    parsed.where(F.col("eventType") == "pp.dataverse.activity")
    .withColumn("d", F.from_json("data_json", dv_schema))
    .select(
        "eventTime",
        F.col("d.entity").alias("entity"),
        F.col("d.operation").alias("operation"),
        F.col("d.userId").alias("user_id"),
        F.col("d.environmentId").alias("environment_id"),
        F.col("d.recordId").alias("record_id"),
        F.col("d.durationMs").cast("long").alias("duration_ms"),
        F.col("d.success").cast("boolean").alias("success"),
    )
)
upsert(dv_df, "dataverse_events", ["entity", "record_id", "eventTime"])

# %%
# --- Tenant-level metrics from BAP forwarder ---
tenant_df = (
    parsed.where(F.col("eventType").startswith("pp.tenant."))
    .select(
        "eventTime",
        "eventType",
        F.col("data_json").alias("payload_json"),
    )
)
upsert(tenant_df, "tenant_metrics", ["eventType", "eventTime"])

# %%
parsed.unpersist()
print("Bronze → Silver complete.")
