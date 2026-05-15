# Lab — Power Platform Telemetry to Fabric

**Goal**: stream Power Platform telemetry through your own Azure pipeline into a Fabric **medallion lakehouse**, with full IaC + CI/CD.

**Time**: ~4 hours.

**You will use**: Bicep, Azure Functions (.NET 8 isolated), Event Hubs, ADLS Gen2, Fabric Eventstream + Notebooks, GitHub Actions.

---

## Architecture recap

```
Power Platform diagnostic settings ──┐
                                     ├──► Event Hubs ──► Eventstream ──► Bronze Lakehouse
Azure Function (BAP API poller) ─────┘                                          │
                                                                                ▼
                                                                Notebook: Bronze → Silver → Gold
                                                                                │
                                                                                ▼
                                                              Power BI (Direct Lake) + Eventhouse
```

See [../docs/architecture.md](../docs/architecture.md) for the full diagram.

---

## Step 1 — Deploy Azure infrastructure

```powershell
az login
az account set --subscription <SUB_ID>

$rg = "rg-pp-telemetry-lab"
$loc = "eastus2"
az group create -n $rg -l $loc

az deployment group create `
  --resource-group $rg `
  --template-file ..\infra\bicep\main.bicep `
  --parameters ..\infra\bicep\main.bicepparam
```

The deployment outputs:

- `eventHubsNamespace` — `evhns-pp-<unique>`
- `functionAppName` — `func-pp-<unique>`
- `storageAccount` — `stppt<unique>`
- `keyVaultName` — `kv-pp-<unique>`

Save these into `$env:` for later steps.

## Step 2 — Configure Power Platform diagnostic settings

For each environment whose telemetry you want to capture:

```powershell
# Requires Microsoft.PowerApps.Administration.PowerShell module
Install-Module Microsoft.PowerApps.Administration.PowerShell -Scope CurrentUser
Add-PowerAppsAccount

$envId = "<environment-guid>"
$ehResourceId = "/subscriptions/<sub>/resourceGroups/$rg/providers/Microsoft.EventHub/namespaces/<evhns>/eventhubs/pp-telemetry"

Set-AdminPowerAppEnvironmentDiagnosticSetting `
  -EnvironmentName $envId `
  -EventHubAuthorizationRuleId "$ehResourceId/authorizationrules/RootManageSharedAccessKey" `
  -EventHubName "pp-telemetry" `
  -Categories "DataverseActivity","PowerAppsActivity","PowerAutomateActivity","CopilotStudioActivity"
```

(If the cmdlet name differs in a newer module version, use the equivalent REST call to `https://api.bap.microsoft.com/.../diagnosticSettings`.)

## Step 3 — Deploy the Azure Function

The function in [../src/functions/PpTelemetryForwarder](../src/functions/PpTelemetryForwarder) polls BAP REST APIs every 15 minutes for tenant analytics not exposed via diagnostic settings (license usage, capacity add-ons, environment lifecycle events) and pushes them to the same Event Hub.

```powershell
cd ..\src\functions\PpTelemetryForwarder
dotnet publish -c Release
func azure functionapp publish $env:functionAppName --dotnet-isolated
```

The function uses **managed identity** to read from Key Vault and write to Event Hubs — no secrets in app settings.

## Step 4 — Create the Fabric workspace + lakehouses

In your Fabric tenant:

1. Create a workspace `pp-telemetry-procode` assigned to your capacity.
2. Create three Lakehouses: `pp_bronze`, `pp_silver`, `pp_gold`.
3. Create an **Eventhouse** named `pp_hot` for sub-second queries on the last 7 days.

## Step 5 — Wire Eventstream

1. **+ New** → **Eventstream** → name `es_pp_telemetry`.
2. **Add source** → **Azure Event Hubs**.
   - Namespace: `$env:eventHubsNamespace`
   - Hub: `pp-telemetry`
   - Auth: shared access key from Key Vault (or managed identity if your tenant supports it).
3. **Add destination** → **Lakehouse** → `pp_bronze`, table `events_raw`, format JSON.
4. **Add destination** → **Eventhouse** → `pp_hot`, table `events_hot`, retention 7d.
5. Publish.

## Step 6 — Run the medallion notebooks

Upload the notebooks from [../notebooks](../notebooks) to the workspace and run them in order:

| Notebook | Purpose | Schedule |
|---|---|---|
| `01_bronze_to_silver.ipynb` | Parse JSON, type-cast, dedupe, write Delta to `pp_silver` | Every 30 min |
| `02_silver_to_gold.ipynb` | Build dim/fact tables: `dim_environment`, `dim_app`, `fact_app_session`, `fact_flow_run` | Every 1 h |
| `03_gold_quality_checks.ipynb` | Great Expectations-style row count + null + freshness checks | Every 1 h, alert on fail |

Wire them into a **Data Factory pipeline** in Fabric for orchestration + retries.

## Step 7 — Power BI Direct Lake model

Build the semantic model from `pp_gold`:

1. Open `pp_gold` Lakehouse → **New semantic model** → pick all `dim_*` and `fact_*` tables.
2. Mark `dim_date` as date table.
3. Star-schema relationships are auto-detected; verify cardinality (1:*).
4. Add measures (DAX) — see [../notebooks/measures.dax](../notebooks/measures.dax) for the seed set.

## Step 8 — CI/CD

`.github/workflows/infra.yml` runs on PR:

- `az bicep build` — syntax check
- `az deployment group what-if` — show change set
- On merge to `main`: `az deployment group create` against the lab subscription using **OIDC workload identity federation** (no secret in GitHub).

`.github/workflows/function.yml` runs on changes under `src/functions/**`:

- `dotnet build` + `dotnet test`
- `func azure functionapp publish` on merge to `main`.

Set the GitHub repo variables:

| Name | Value |
|---|---|
| `AZURE_CLIENT_ID` | App registration (federated) |
| `AZURE_TENANT_ID` | Tenant GUID |
| `AZURE_SUBSCRIPTION_ID` | Lab subscription |
| `AZURE_RG` | `rg-pp-telemetry-lab` |
| `FUNCTION_APP_NAME` | output of Step 1 |

## Cleanup

```powershell
az group delete -n $rg --yes --no-wait
```

Then in Fabric: delete the workspace and pause the capacity.

## Troubleshooting

| Symptom | Fix |
|---|---|
| Diagnostic setting cmdlet returns 403 | Caller needs Power Platform admin + Owner on the Event Hub. |
| Eventstream shows 0 events/sec | Confirm the hub has `Send` permission for the AAD app PP uses (`Microsoft Power Platform`). |
| Notebook fails on `pp_silver` writes | Lakehouse SQL endpoint can lag — wait 30 s after creation, or use Spark API directly. |
| Function cold start > 30 s | Switch from Consumption to Flex Consumption (already default in `main.bicep`). |
