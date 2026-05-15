# Lab — Power Platform Telemetry to Fabric

**Goal**: Stream Power Platform telemetry through your own Azure pipeline into a Fabric **medallion lakehouse**, with full IaC + CI/CD.

**Time**: ~4 hours end-to-end.

**You will use**: Entra ID, Bicep, Azure Functions (.NET 8 isolated), Event Hubs, Key Vault, Fabric Eventstream + Lakehouse + Eventhouse + Notebooks, GitHub Actions.

---

## Prerequisites

Before you start, confirm you have everything listed in [../docs/prerequisites.md](../docs/prerequisites.md):

- Azure subscription (Contributor + User Access Administrator)
- Microsoft Fabric capacity (F2+ or 60-day trial)
- Power Platform tenant with at least one environment
- Local tools: Azure CLI, .NET 8 SDK, Azure Functions Core Tools v4, Bicep, Python 3.11+
- Entra ID permissions to create app registrations

---

## Architecture overview

```
Power Platform
│
├── Diagnostic settings (per env) ──► Event Hubs ──► Eventstream ──► Bronze Lakehouse
│                                                                          │
└── BAP REST APIs ──► Azure Function ──► Event Hubs ──┘                    ▼
                          │                               Notebook: Bronze → Silver → Gold
                          │                                            │
                          ├── Key Vault (secrets)                      ▼
                          ├── App Insights (traces)       Power BI (Direct Lake) + Eventhouse (KQL)
                          └── UAMI (identity)
```

Full architecture: [../docs/architecture.md](../docs/architecture.md) | [README architecture section](../README.md#architecture)

---

## Step 0 — Create an Entra ID app registration for Power Platform

The Azure Function authenticates to the BAP REST APIs using a service principal. This step creates the app registration and grants it Power Platform admin permissions.

> **Detailed walkthrough**: See [../docs/app-registration.md](../docs/app-registration.md) for screenshots and troubleshooting.

### 0.1 — Register the application in Entra ID

1. Go to [Azure Portal → Entra ID → App registrations](https://portal.azure.com/#view/Microsoft_AAD_IAM/ActiveDirectoryMenuBlade/~/RegisteredApps).
2. Click **+ New registration**.
3. Fill in:
   - **Name**: `pp-telemetry-lab-sp`
   - **Supported account types**: Single tenant
   - **Redirect URI**: Leave blank
4. Click **Register**. Note the **Application (client) ID** and **Directory (tenant) ID**.

### 0.2 — Add API permissions

1. In the app registration, go to **API permissions** → **+ Add a permission**.
2. Select **APIs my organization uses** → search for `PowerPlatform` → select **Power Platform API** (also listed as `https://api.powerplatform.com`).
3. Select **Delegated permissions** → check `User.Read` (or `user_impersonation` if available).
4. Click **Add permissions** → **Grant admin consent for \<your tenant\>**.

> **Note**: For tenant-level analytics (BAP APIs), the service principal also needs to be registered as a **Power Platform management application**. See step 0.4.

### 0.3 — Create a client secret

1. Go to **Certificates & secrets** → **+ New client secret**.
2. Description: `pp-telemetry-lab`, Expiry: 12 months.
3. Click **Add**. **Copy the secret value immediately** — you won't see it again.

### 0.4 — Register as a Power Platform management application

This grants the service principal permission to call the BAP admin REST APIs at `https://api.bap.microsoft.com`.

```powershell
# Requires the Power Apps admin PowerShell module
Install-Module -Name Microsoft.PowerApps.Administration.PowerShell -Scope CurrentUser -Force
Add-PowerAppsAccount   # sign in with a Power Platform admin account

# Register your app as a management app
New-PowerAppManagementApp -ApplicationId "<your-client-id>"
```

Verify it was registered:

```powershell
Get-PowerAppManagementApp | Where-Object { $_.ApplicationId -eq "<your-client-id>" }
```

> **Troubleshooting**: If `New-PowerAppManagementApp` returns 403, the signed-in user must be a Power Platform admin or Global admin.

---

## Step 1 — Deploy Azure infrastructure with Bicep

The Bicep template in `infra/bicep/main.bicep` provisions all Azure resources in a single deployment:

- Resource Group
- Log Analytics workspace
- Application Insights (workspace-based)
- Storage account (ADLS Gen2)
- Event Hubs namespace + hub (`pp-telemetry`)
- Function App (Flex Consumption, .NET 8 isolated)
- Key Vault (RBAC mode)
- User-Assigned Managed Identity (UAMI)
- RBAC role assignments (Key Vault Secrets User, Event Hubs Data Sender, Storage Blob Data Contributor)

### 1.1 — Login and set subscription

```powershell
az login
az account set --subscription "<YOUR_SUBSCRIPTION_ID>"
```

### 1.2 — Create resource group

```powershell
$rg  = "rg-pp-telemetry-lab"
$loc = "eastus2"

az group create --name $rg --location $loc
```

### 1.3 — Deploy

```powershell
az deployment group create `
  --resource-group $rg `
  --template-file infra/bicep/main.bicep `
  --parameters infra/bicep/main.bicepparam `
  --parameters adminPrincipalId="$(az ad signed-in-user show --query id -o tsv)"
```

### 1.4 — Save deployment outputs

```powershell
$outputs = az deployment group show -g $rg -n main --query properties.outputs -o json | ConvertFrom-Json

$funcName = $outputs.functionAppName.value
$kvName   = $outputs.keyVaultName.value
$evhNs    = $outputs.eventHubsNamespace.value
$aiName   = $outputs.appInsightsName.value

Write-Host "Function App : $funcName"
Write-Host "Key Vault    : $kvName"
Write-Host "Event Hubs NS: $evhNs"
Write-Host "App Insights : $aiName"
```

Save these — you'll use them in every subsequent step.

---

## Step 2 — Store secrets in Key Vault

The Function App reads secrets from Key Vault via managed identity — never from app settings directly.

### 2.1 — Store the Power Platform service principal secret

```powershell
az keyvault secret set `
  --vault-name $kvName `
  --name "pp-tenant-sp-secret" `
  --value "<paste-your-client-secret-from-step-0.3>"
```

### 2.2 — Store the Fabric Eventstream connection string

> You'll get this in **Step 5** when you create the Eventstream. Come back here after copying the SAS connection string.

```powershell
az keyvault secret set `
  --vault-name $kvName `
  --name "fabric-eventstream-cs" `
  --value "<your-eventstream-SAS-connection-string>"
```

---

## Step 3 — Configure Function App settings

The Function App needs to know which Power Platform tenant to poll, which app registration to use, and where to send events.

```powershell
az functionapp config appsettings set `
  --name $funcName `
  --resource-group $rg `
  --settings `
    PP_TENANT_ID="<your-pp-tenant-id>" `
    PP_CLIENT_ID="<your-app-registration-client-id-from-step-0>" `
    PP_CLIENT_SECRET_NAME="pp-tenant-sp-secret" `
    EVENTHUB_CONNECTION_STRING="@Microsoft.KeyVault(SecretUri=https://$kvName.vault.azure.net/secrets/fabric-eventstream-cs/)"
```

**What each setting does**:

| Setting | Purpose |
|---|---|
| `PP_TENANT_ID` | The Power Platform tenant GUID (may differ from your Azure tenant) |
| `PP_CLIENT_ID` | Client ID of the app registration created in Step 0 |
| `PP_CLIENT_SECRET_NAME` | Name of the Key Vault secret holding the client secret |
| `EVENTHUB_CONNECTION_STRING` | Key Vault reference — Function App resolves it at runtime using UAMI |

> **Important**: After setting `EVENTHUB_CONNECTION_STRING`, the Function App must restart to pick up the Key Vault reference. A restart happens automatically when settings change, but if you see stale values, force it:
>
> ```powershell
> az functionapp restart --name $funcName --resource-group $rg
> ```

---

## Step 4 — Build and deploy the Azure Function

### 4.1 — Build locally

```powershell
cd src/functions/PpTelemetryForwarder
dotnet restore
dotnet build -c Release
```

### 4.2 — Deploy to Azure

```powershell
dotnet publish -c Release
func azure functionapp publish $funcName --dotnet-isolated
```

> **⚠ Flex Consumption note**: Always use `func azure functionapp publish` for Flex Consumption plans. Manual zip-deploy or `az functionapp deployment` can fail with path encoding issues on Windows.

### 4.3 — Verify the deployment

```powershell
# Check that functions are listed
func azure functionapp list-functions $funcName

# Expected output:
#   PollLicenseUsage  -  timerTrigger
#   PollEnvironmentLifecycle  -  timerTrigger
#   HealthCheck  -  httpTrigger
```

Test the health endpoint:

```powershell
$funcUrl = (az functionapp show -n $funcName -g $rg --query defaultHostName -o tsv)
Invoke-RestMethod "https://$funcUrl/api/health"
```

---

## Step 5 — Create the Fabric workspace and artifacts

These steps are performed **manually in the Fabric portal** ([app.fabric.microsoft.com](https://app.fabric.microsoft.com)).

### 5.1 — Create a Fabric workspace

1. Open Fabric → click **Workspaces** (left nav) → **+ New workspace**.
2. Name: `pp-telemetry-lab`.
3. Under **Advanced**, assign it to your Fabric capacity (F2+ or Trial).
4. Click **Apply**.

### 5.2 — Create Lakehouses

Inside the workspace, create three Lakehouses for the medallion architecture:

1. Click **+ New item** → **Lakehouse** → name: `pp_bronze` → **Create**.
2. Repeat for `pp_silver`.
3. Repeat for `pp_gold`.

### 5.3 — Create an Eventhouse

1. Click **+ New item** → **Eventhouse** → name: `pp_hot` → **Create**.
2. This automatically creates a KQL database with the same name.
3. Note the **Query URI** (e.g., `trd-xxxxx.z6.kusto.fabric.microsoft.com`) — you'll use it for KQL queries.

### 5.4 — Create the Eventstream

1. Click **+ New item** → **Eventstream** → name: `pp-telemetry-stream` → **Create**.

2. **Add a source — Custom Endpoint**:
   - In the Eventstream editor, click **+ Add source** → **Custom endpoint** (also called "Custom App" in some UIs).
   - Name: `azure-function-input`.
   - After creation, click the source node → copy the **Event Hub-compatible connection string** (starts with `Endpoint=sb://...`).

3. **Store the connection string in Key Vault** (go back to Step 2.2):
   ```powershell
   az keyvault secret set `
     --vault-name $kvName `
     --name "fabric-eventstream-cs" `
     --value "<paste-the-SAS-connection-string>"
   ```
   Then restart the Function App so it picks up the new secret:
   ```powershell
   az functionapp restart --name $funcName --resource-group $rg
   ```

4. **Add destination 1 — Lakehouse**:
   - Click **+ Add destination** → **Lakehouse**.
   - Workspace: `pp-telemetry-lab`, Lakehouse: `pp_bronze`.
   - Table: `events_raw` (create new).
   - Input data format: **JSON**.

5. **Add destination 2 — Eventhouse**:
   - Click **+ Add destination** → **Eventhouse** (or **KQL Database**).
   - Database: `pp_hot`, Table: `pp_telemetry_raw` (create new).
   - Retention: 7 days (default).

6. Click **Publish** to activate the Eventstream.

---

## Step 5.5 — Enable Link to Microsoft Fabric (Dataverse mirror)

"Link to Microsoft Fabric" mirrors Dataverse tables into your Fabric workspace as **read-only Delta tables** in OneLake — zero ETL, near-real-time sync. This brings CoE Starter Kit inventory data (apps, flows, makers, connectors, environments) into the medallion pipeline.

### Prerequisites

- CoE Starter Kit installed in at least one Power Platform environment ([setup guide](https://learn.microsoft.com/en-us/power-platform/guidance/coe/setup)).
- The environment must have a Dataverse database provisioned.
- Fabric capacity assigned to the target workspace.

### 5.5.1 — Enable the link from Power Platform admin center

1. Open [Power Platform admin center](https://admin.powerplatform.microsoft.com/) → **Environments** → select the environment with CoE Kit.
2. Click **Settings** → **Product** → **Features**.
3. Under **Link to Microsoft Fabric**, toggle **On**.
4. Click **Save**.

### 5.5.2 — Create the link in Fabric

1. Open the `pp-telemetry-lab` workspace in Fabric.
2. Click **+ New item** → **Shortcuts** → **Microsoft Dataverse**.
3. Sign in when prompted and select the environment.
4. Select the tables to mirror:

| Dataverse Table (CoE Kit) | Display Name | Purpose |
|---|---|---|
| `admin_app` | Power Apps Inventory | App id, name, owner, created, modified, connector list |
| `admin_flow` | Flow Inventory | Flow id, name, owner, status, trigger type |
| `admin_maker` | Maker Inventory | User id, display name, email, department, city |
| `admin_environment` | Environment Inventory | Environment id, name, type, region, SKU |
| `admin_connector` | Connector Inventory | Connector id, name, tier (standard/premium), publisher |
| `admin_dlpolicies` | DLP Policy Inventory | Policy id, name, environments, connector groups |
| `admin_appuserlaunch` | App User Launch | App id, user id, launch date — for MAU calculation |

5. Click **Create**. Fabric begins the initial sync — typically 5–30 minutes depending on data volume.

> **Note**: If you don't have the CoE Starter Kit, you can still mirror native Dataverse tables like `systemuser`, `workflow`, `canvasapp`, `solutioncomponent`. The notebooks handle both CoE and native schemas.

### 5.5.3 — Verify the mirrored tables

In the `pp-telemetry-lab` workspace you should see a new **Mirrored Database** item. Open it and confirm:

```
Mirrored Dataverse DB
├── Tables/
│   ├── admin_app
│   ├── admin_flow
│   ├── admin_maker
│   ├── admin_environment
│   ├── admin_connector
│   ├── admin_dlpolicies
│   └── admin_appuserlaunch
```

Query a quick count in a notebook:

```python
df = spark.read.format("delta").table("pp_dataverse_mirror.admin_app")
print(f"Apps mirrored: {df.count()}")
```

### 5.5.4 — How this fits the medallion pipeline

The mirrored tables are **already in Delta format in OneLake** — they act as a parallel Bronze source alongside the Eventstream-fed `pp_bronze.events_raw`. The medallion notebooks (updated in Step 8) read from both:

```
Eventstream → pp_bronze.events_raw  ──┐
                                      ├── Silver (typed, deduped)
Dataverse mirror → admin_*  ──────────┘           │
                                                   ▼
                                              Gold (star schema)
                                                   │
                                              Direct Lake → PBI
```

---

## Step 6 — Configure Power Platform diagnostic settings

For each Power Platform environment whose telemetry you want to capture:

```powershell
Install-Module Microsoft.PowerApps.Administration.PowerShell -Scope CurrentUser -Force
Add-PowerAppsAccount

$envId = "<environment-guid>"
$ehResourceId = "/subscriptions/<sub>/resourceGroups/$rg/providers/Microsoft.EventHub/namespaces/$evhNs/eventhubs/pp-telemetry"

Set-AdminPowerAppEnvironmentDiagnosticSetting `
  -EnvironmentName $envId `
  -EventHubAuthorizationRuleId "$ehResourceId/authorizationrules/RootManageSharedAccessKey" `
  -EventHubName "pp-telemetry" `
  -Categories "DataverseActivity","PowerAppsActivity","PowerAutomateActivity","CopilotStudioActivity"
```

> **Alternative (REST API)**:
> ```
> PUT https://api.bap.microsoft.com/providers/Microsoft.BusinessAppPlatform/environments/{envId}/diagnosticSettings?api-version=2023-06-01
> ```
> See [BAP diagnostic settings docs](https://learn.microsoft.com/en-us/power-platform/admin/self-service-analytics) for the full payload.

---

## Step 7 — Verify end-to-end data flow

After the Function's first timer fire (within 15 minutes of deployment), data should appear in both destinations.

### 7.1 — Check Function execution in App Insights

```powershell
az monitor app-insights query `
  --app $aiName `
  --resource-group $rg `
  --analytics-query "traces | where timestamp > ago(30m) | where message has 'Published' | project timestamp, message | order by timestamp desc | take 10"
```

You should see messages like:
```
Published 1 pp.tenant.licenseUsage events
Published 5 pp.environment.lifecycle events
```

### 7.2 — Query the Eventhouse (KQL)

Open the KQL queryset in Fabric and run:

```kusto
pp_telemetry_raw
| where ingestion_time() > ago(1h)
| summarize count() by eventType
| order by count_ desc
```

Expected event types: `pp.environment.lifecycle`, `pp.tenant.licenseUsage`.

### 7.3 — Check the Bronze Lakehouse

In Fabric, open `pp_bronze` → **Tables** → `events_raw`. You should see rows with JSON payloads.

### 7.4 — Test the health endpoint

```powershell
Invoke-RestMethod "https://$funcUrl/api/health"
# Returns: { status: "Healthy", timestamp: "...", functions: [...] }
```

### Troubleshooting

| Symptom | Likely cause | Fix |
|---|---|---|
| No events in Eventhouse after 30 min | Eventstream not connected to source | Re-check the Custom Endpoint connection string matches what's in Key Vault |
| Function logs show `403 Forbidden` on BAP API | App registration not registered as management app | Re-run `New-PowerAppManagementApp` (Step 0.4) |
| Function logs show `SecretNotFound` | Key Vault secret name mismatch or UAMI lacks `Key Vault Secrets User` | Check `az keyvault secret list --vault-name $kvName` and role assignments |
| Eventstream shows 0 events/sec | Event Hub auth issue | Confirm the connection string has `Send` permission |
| `func azure functionapp publish` fails | Wrong .NET SDK or stale tools | Run `dotnet --version` (must be 8.x), update with `npm i -g azure-functions-core-tools@4` |
| Diagnostic settings return 403 | Caller needs PP admin + Owner on Event Hub | Ensure the signed-in account is Power Platform admin |
| Function cold start > 30s | Normal for first invocation on Flex Consumption | Subsequent calls are fast; consider Always Ready instances for production |

---

## Step 8 — Run the medallion notebooks

Upload the notebooks from [../notebooks](../notebooks) to the `pp-telemetry-lab` Fabric workspace.

### 8.1 — Upload notebooks

1. In the Fabric workspace, click **+ New item** → **Import notebook**.
2. Upload all three `.py` files from `notebooks/`.

### 8.2 — Configure and run

Each notebook expects a Lakehouse attached. In the notebook editor:
1. Click **Lakehouses** (left panel) → **Add** → select `pp_bronze` (for notebook 01), `pp_silver` (for 02), `pp_gold` (for 03).

Run in order:

| # | Notebook | Input | Output | Schedule |
|---|---|---|---|---|
| 0 | `00_dataverse_mirror.py` | Dataverse mirror tables (`admin_app`, `admin_flow`, etc.) | `pp_silver` (`dv_apps`, `dv_flows`, `dv_makers`, `dv_environments`, `dv_connectors`, `dv_dlp_policies`, `dv_app_launches`) | Every 30 min |
| 1 | `01_bronze_to_silver.py` | `pp_bronze.events_raw` | `pp_silver` (typed Delta, one table per event type) | Every 30 min |
| 2 | `02_silver_to_gold.py` | `pp_silver.*` | `pp_gold` (`dim_environment`, `dim_app`, `dim_maker`, `dim_connector`, `dim_dlp_policy`, `fact_app_session`, `fact_flow_run`, `fact_copilot_message`, `fact_app_launch`) | Hourly |
| 3 | `03_gold_quality_checks.py` | `pp_gold.*` | Row count, null %, freshness assertions | Hourly, alert on fail |

### 8.3 — Schedule with Data Factory pipeline (optional)

1. In the workspace, click **+ New item** → **Data pipeline**.
2. Add four **Notebook** activities in sequence (00 → 01 → 02 → 03).
3. Set a schedule trigger (e.g., every 30 minutes).
4. Configure alerts on failure.

---

## Step 9 — Build the Power BI Direct Lake model

### 9.1 — Create the semantic model

1. Open the `pp_gold` Lakehouse in Fabric.
2. Click **New semantic model** (top bar).
3. Select all `dim_*` and `fact_*` tables → **Confirm**.

### 9.2 — Configure relationships

In the model view:
1. Verify star-schema relationships (auto-detected):
   - `fact_app_session[environmentId]` → `dim_environment[environmentId]` (many-to-one)
   - `fact_flow_run[environmentId]` → `dim_environment[environmentId]` (many-to-one)
   - `fact_app_session[appId]` → `dim_app[appId]` (many-to-one)
2. Mark `dim_date` as the **date table** (if present).

### 9.3 — Add DAX measures

Open the `notebooks/measures.dax` file — it contains 30+ measures. Add them to the semantic model:

```dax
// Example measures from the file:
Adoption Index = DIVIDE([MAU], [Licensed Users], 0)
Error Rate %   = DIVIDE([Error Count], [Total Runs], 0) * 100
Cost Per BU    = DIVIDE([Total Capacity Cost], DISTINCTCOUNT(dim_environment[businessUnit]))
```

### 9.4 — Build reports

Create a Power BI report on top of the semantic model. Suggested pages:
- **Executive Dashboard**: Adoption Index, MAU trend, Business Value
- **Governance**: Risk Posture, DLP violations, unowned apps
- **Operations**: Reliability, p95 flow duration, error rate by environment
- **Capacity**: Cost-to-Serve by BU, license utilization

---

## Step 10 — Set up CI/CD with GitHub Actions

### 10.1 — Create a federated credential for OIDC

1. In your app registration (or create a new one), go to **Certificates & secrets** → **Federated credentials** → **+ Add credential**.
2. Select **GitHub Actions deploying Azure resources**.
3. Fill in:
   - Organization: `<your-github-org>`
   - Repository: `<your-repo-name>`
   - Entity type: **Branch** → `main`
4. Click **Add**.

### 10.2 — Set GitHub repository variables

Go to **Settings** → **Secrets and variables** → **Actions** → **Variables**:

| Name | Value |
|---|---|
| `AZURE_CLIENT_ID` | App registration client ID (federated credential) |
| `AZURE_TENANT_ID` | Your Azure tenant GUID |
| `AZURE_SUBSCRIPTION_ID` | Lab subscription GUID |
| `AZURE_RG` | `rg-pp-telemetry-lab` |
| `FUNCTION_APP_NAME` | Output from Step 1 (e.g., `func-pptel-xxxxx`) |

### 10.3 — How the workflows work

`.github/workflows/infra.yml` — runs on PRs and merges:
- `az bicep build` — syntax validation
- `az deployment group what-if` — preview changes
- On merge to `main`: `az deployment group create`

`.github/workflows/function.yml` — runs on changes under `src/functions/**`:
- `dotnet build` + `dotnet test`
- On merge to `main`: `func azure functionapp publish`

Both use **OIDC workload identity federation** — no long-lived secrets stored in GitHub.

---

## Cleanup

```powershell
# Delete all Azure resources
az group delete --name $rg --yes --no-wait

# In Fabric: delete the workspace and pause/delete the capacity
```

---

## Next steps

- **Add diagnostic settings** for more environments (Step 6) to broaden coverage
- **Add your vertical** by copying [docs/verticals/_template.md](../docs/verticals/_template.md) and adding Tier-3 KPIs
- **Extend the Gold layer** with additional dim/fact tables for your specific needs
- **Configure alerts** on the data quality notebook (Step 8.3) for production monitoring
- **Read the business context**: [docs/business-use-case.md](../docs/business-use-case.md) for full persona definitions and KPI catalog
