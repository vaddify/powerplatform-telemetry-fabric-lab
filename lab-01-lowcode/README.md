# Lab 01 — Low-code / no-code track

**Goal**: land Power Platform telemetry into a Microsoft Fabric Lakehouse and visualize it in Power BI **without writing custom code**.

**Time**: ~2 hours.

**You will use**: Power Platform admin center, Power Apps maker portal, Application Insights, Fabric workspace, Dataflow Gen2, Power BI Direct Lake.

---

## Step 1 — Wire Application Insights into Power Platform

1. Open <https://admin.powerplatform.microsoft.com>.
2. Pick the environment you want to instrument → **Settings** → **Product** → **Application Insights**.
3. Click **+ New connection**, select your Azure subscription and the App Insights resource provisioned in [prerequisites](../docs/prerequisites.md).
4. Toggle on:
   - Power Apps (Canvas) — sessions, errors, custom traces
   - Power Apps (Model-driven) — page loads, command bar
   - Power Automate — flow runs, action telemetry
   - Dataverse — plug-in execution, API calls
5. Save. Allow ~30 minutes for telemetry to start flowing.

**Verify**: in Azure Portal → your App Insights → **Logs**, run

```kusto
traces
| where timestamp > ago(1h)
| where customDimensions has "PowerApps"
| take 50
```

## Step 2 — Enable "Link to Microsoft Fabric" on Dataverse

1. Open <https://make.powerapps.com>, pick the same environment.
2. Left rail → **Tables**.
3. Top bar → **Analyze** → **Link to Microsoft Fabric**.
4. Pick the target Fabric workspace (must be on F-SKU capacity).
5. Select the tables to mirror. For this lab pick:
   - `Account`, `Contact`
   - All CoE Kit tables prefixed `admin_*` (App, Flow, Maker, Environment)
6. Click **Save**. Initial sync takes 5–15 minutes.

**Verify**: in your Fabric workspace, a new **Lakehouse** named `<env>_dataverse` appears with Delta tables.

## Step 3 — Install / refresh the CoE Starter Kit

If you don't already have CoE Kit:

1. Download from <https://aka.ms/CoEStarterKit>.
2. Import `CenterofExcellenceCoreComponents_*.zip` into your CoE environment.
3. Run the **Admin | Sync Template v4 (Driver)** flow once manually so tables populate.

These tables are now mirrored to Fabric via Step 2.

## Step 4 — Create the Lakehouse + ingest App Insights

In your Fabric workspace:

1. **+ New** → **Lakehouse**, name it `pp_telemetry_lh`.
2. Open the Lakehouse → **Get data** → **New Dataflow Gen2**.
3. **Get data** → **Azure** → **Azure Data Explorer (Kusto)**.
   - Cluster URL: your App Insights workspace's ADX query endpoint (Logs → ⓘ → "Query API").
   - Database: the Log Analytics workspace name.
   - Query:
     ```kusto
     union traces, requests, exceptions, dependencies
     | where timestamp > ago(7d)
     | project timestamp, itemType, name, resultCode, duration, customDimensions, operation_Id, cloud_RoleName
     ```
4. Set **Destination** = the `pp_telemetry_lh` Lakehouse, table `app_insights_raw`, **Append** mode.
5. **Schedule refresh**: every 1 hour.

## Step 5 — Build the Power BI semantic model (Direct Lake)

1. In `pp_telemetry_lh` → top right → **New semantic model**.
2. Pick tables: `app_insights_raw`, `admin_app`, `admin_flow`, `admin_maker`, `admin_environment`, `Account`.
3. Open the model → **Manage relationships**:
   - `app_insights_raw[cloud_RoleName]` → `admin_app[name]`
   - `admin_app[ownerid]` → `admin_maker[id]`
4. Add measures (DAX):
   ```dax
   App Sessions = COUNTROWS(FILTER(app_insights_raw, app_insights_raw[itemType] = "request"))
   Flow Failures = CALCULATE(COUNTROWS(app_insights_raw), app_insights_raw[resultCode] >= 400)
   Active Makers 30d = CALCULATE(DISTINCTCOUNT(admin_app[ownerid]), DATESINPERIOD('Date'[Date], TODAY(), -30, DAY))
   ```

## Step 6 — Build the report

1. From the semantic model → **+ Create report**.
2. Suggested visuals:
   - Line chart: `App Sessions` by day
   - Bar chart: top 10 apps by session count
   - Card: `Active Makers 30d`
   - Matrix: flow runs × `resultCode` heatmap

## Cleanup

- Pause / delete the Fabric capacity if you used a trial.
- Disconnect Application Insights link in admin center.
- Remove "Link to Fabric" from Power Apps maker portal → Tables → Analyze.

## Troubleshooting

| Symptom | Fix |
|---|---|
| App Insights shows no Power Platform telemetry after 1h | Confirm the env is in the same tenant as the AI resource; re-save the connection. |
| "Link to Fabric" greyed out | Workspace must be on Fabric capacity (not Pro/PPU); user needs Dataverse System Administrator. |
| Dataflow refresh fails on Kusto | Use the workspace's ADX-style URL, not the App Insights blade URL; auth must be OAuth2. |
| Direct Lake falls back to DirectQuery | Tables must be Delta with V-Order; check semantic model storage mode. |

## Next steps

- Promote the report to an **App** in Power BI for governed distribution.
- Wire **Microsoft Purview** to the workspace for lineage.
- Move on to [lab-02-procode](../lab-02-procode) for streaming + custom enrichment.
