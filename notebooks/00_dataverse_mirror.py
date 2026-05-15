# Databricks/Fabric notebook source — PySpark
# Notebook: 00_dataverse_mirror
# Reads mirrored Dataverse / CoE Kit tables via "Link to Microsoft Fabric"
# and writes cleansed staging tables into pp_silver for downstream Gold joins.
# Run BEFORE 02_silver_to_gold.py so Gold dims can reference CoE inventory.

# %%
from pyspark.sql import functions as F
from delta.tables import DeltaTable

# The mirrored database name matches what Fabric creates when you set up
# the Dataverse link. Adjust if your workspace uses a different name.
MIRROR_DB = "pp_dataverse_mirror"
SILVER_DB = "pp_silver"

spark.sql(f"CREATE SCHEMA IF NOT EXISTS {SILVER_DB}")

# %%
# ---------------------------------------------------------------------------
# Helper: read a mirrored table, apply column renames + types, write to Silver
# ---------------------------------------------------------------------------
def stage_mirror(source_table, target_table, select_expr, keys):
    """Read from Dataverse mirror, cleanse, and merge into Silver."""
    full_source = f"{MIRROR_DB}.{source_table}"
    full_target = f"{SILVER_DB}.{target_table}"

    if not spark.catalog.tableExists(full_source):
        print(f"⚠ Skipping {full_source} — table not found (CoE Kit may not be installed)")
        return

    df = spark.read.table(full_source).selectExpr(*select_expr)

    if not spark.catalog.tableExists(full_target):
        df.write.format("delta").mode("overwrite").saveAsTable(full_target)
        print(f"✓ Created {full_target} ({df.count()} rows)")
        return

    target = DeltaTable.forName(spark, full_target)
    cond = " AND ".join([f"t.{k} = s.{k}" for k in keys])
    (target.alias("t")
        .merge(df.alias("s"), cond)
        .whenMatchedUpdateAll()
        .whenNotMatchedInsertAll()
        .execute())
    print(f"✓ Merged into {full_target}")

# %%
# ---------------------------------------------------------------------------
# CoE Kit tables → Silver staging
# ---------------------------------------------------------------------------

# Apps inventory
stage_mirror(
    source_table="admin_app",
    target_table="dv_apps",
    select_expr=[
        "admin_appid AS app_id",
        "admin_displayname AS app_name",
        "admin_apptypedisplayname AS app_type",
        "admin_owner AS owner_id",
        "admin_appownerdisplayname AS owner_name",
        "admin_appenvironment AS environment_id",
        "admin_appconnectors AS connectors",
        "admin_appcreatedon AS created_date",
        "admin_appmodifiedon AS modified_date",
        "admin_appsharedusercount AS shared_user_count",
        "admin_applastlauncheddate AS last_launched_date",
    ],
    keys=["app_id"],
)

# %%
# Flows inventory
stage_mirror(
    source_table="admin_flow",
    target_table="dv_flows",
    select_expr=[
        "admin_flowid AS flow_id",
        "admin_displayname AS flow_name",
        "admin_flowowner AS owner_id",
        "admin_flowownerdisplayname AS owner_name",
        "admin_flowenvironment AS environment_id",
        "admin_flowstate AS state",
        "admin_flowtriggertype AS trigger_type",
        "admin_flowconnectors AS connectors",
        "admin_flowcreatedon AS created_date",
        "admin_flowmodifiedon AS modified_date",
    ],
    keys=["flow_id"],
)

# %%
# Makers inventory
stage_mirror(
    source_table="admin_maker",
    target_table="dv_makers",
    select_expr=[
        "admin_makerid AS maker_id",
        "admin_displayname AS display_name",
        "admin_userprincipalname AS upn",
        "admin_city AS city",
        "admin_country AS country",
        "admin_department AS department",
        "admin_firsttimemaker AS first_time_maker",
    ],
    keys=["maker_id"],
)

# %%
# Environments inventory
stage_mirror(
    source_table="admin_environment",
    target_table="dv_environments",
    select_expr=[
        "admin_environmentid AS environment_id",
        "admin_displayname AS environment_name",
        "admin_environmentsku AS sku",
        "admin_environmentregion AS region",
        "admin_environmenttype AS env_type",
        "admin_environmentcreatedon AS created_date",
        "admin_environmentmakercountalltime AS maker_count",
        "admin_environmentappcountalltime AS app_count",
        "admin_environmentflowcountalltime AS flow_count",
    ],
    keys=["environment_id"],
)

# %%
# Connectors inventory
stage_mirror(
    source_table="admin_connector",
    target_table="dv_connectors",
    select_expr=[
        "admin_connectorid AS connector_id",
        "admin_displayname AS connector_name",
        "admin_connectortier AS tier",
        "admin_publisher AS publisher",
    ],
    keys=["connector_id"],
)

# %%
# DLP policies
stage_mirror(
    source_table="admin_dlpolicies",
    target_table="dv_dlp_policies",
    select_expr=[
        "admin_dlppolicyid AS policy_id",
        "admin_displayname AS policy_name",
        "admin_environmenttype AS scope",
        "admin_numberofenvironments AS environment_count",
        "admin_numberofconnectorsinbusinessgroup AS connectors_business",
        "admin_numberofconnectorsinnondatagroup AS connectors_nondata",
        "admin_numberofconnectorsinblockedgroup AS connectors_blocked",
    ],
    keys=["policy_id"],
)

# %%
# App user launches (for MAU calculation)
stage_mirror(
    source_table="admin_appuserlaunch",
    target_table="dv_app_launches",
    select_expr=[
        "admin_appuserlaunchid AS launch_id",
        "admin_app AS app_id",
        "admin_user AS user_id",
        "admin_launchdate AS launch_date",
    ],
    keys=["launch_id"],
)

# %%
# ---------------------------------------------------------------------------
# Summary
# ---------------------------------------------------------------------------
print("\n=== Dataverse Mirror → Silver Summary ===")
for t in ["dv_apps", "dv_flows", "dv_makers", "dv_environments", "dv_connectors", "dv_dlp_policies", "dv_app_launches"]:
    full = f"{SILVER_DB}.{t}"
    if spark.catalog.tableExists(full):
        cnt = spark.read.table(full).count()
        print(f"  {full}: {cnt:,} rows")
    else:
        print(f"  {full}: (not created)")

print("\nDataverse mirror → Silver staging complete.")
