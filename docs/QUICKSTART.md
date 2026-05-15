# Quickstart — See data flow in 15 minutes

This guide gets you from zero to **live Power Platform telemetry in Fabric** as fast as possible. For the full lab experience, see [lab/](../lab/).

## Prerequisites

- Azure subscription with Contributor access
- Microsoft Fabric workspace on F2+ capacity (or 60-day trial)
- Power Platform tenant with at least one environment
- Entra ID app registration with `https://api.powerplatform.com/.default` permission — see [app-registration.md](./app-registration.md)
- Local tools: Azure CLI, .NET 8 SDK, Azure Functions Core Tools v4, Bicep

## Step 1 — Deploy Azure resources (5 min)

```powershell
az login
az account set --subscription "<YOUR_SUB_ID>"

# Create resource group
az group create -n rg-pp-telemetry-lab -l eastus2

# Deploy all infrastructure (Event Hubs, Function App, Key Vault, UAMI, Storage)
az deployment group create `
  --resource-group rg-pp-telemetry-lab `
  --template-file infra/bicep/main.bicep `
  --parameters infra/bicep/main.bicepparam `
  --parameters adminPrincipalId="$(az ad signed-in-user show --query id -o tsv)"
```

Note the outputs — you'll need `functionAppName` and `keyVaultName`.

## Step 2 — Store your secrets in Key Vault (2 min)

```powershell
$kvName = "<keyVaultName from Step 1>"

# Store your Fabric Eventstream connection string
az keyvault secret set --vault-name $kvName `
  --name "fabric-eventstream-cs" `
  --value "<your-eventstream-SAS-connection-string>"

# Store your Power Platform service principal secret
az keyvault secret set --vault-name $kvName `
  --name "pp-tenant-sp-secret" `
  --value "<your-app-registration-secret>"
```

## Step 3 — Configure and deploy the Function (3 min)

```powershell
$funcName = "<functionAppName from Step 1>"

# Set Power Platform tenant config
az functionapp config appsettings set -n $funcName -g rg-pp-telemetry-lab --settings `
  PP_TENANT_ID="<your-pp-tenant-id>" `
  PP_CLIENT_ID="<your-app-registration-client-id>" `
  PP_CLIENT_SECRET_NAME="pp-tenant-sp-secret" `
  EVENTHUB_CONNECTION_STRING="@Microsoft.KeyVault(SecretUri=https://$kvName.vault.azure.net/secrets/fabric-eventstream-cs/)"

# Build and deploy
cd src/functions/PpTelemetryForwarder
dotnet publish -c Release
func azure functionapp publish $funcName --dotnet-isolated
```

## Step 4 — Wire Fabric Eventstream (3 min)

1. In your Fabric workspace, create an **Eventstream** → name it `pp-telemetry-stream`.
2. **Add source** → **Custom endpoint** → copy the SAS connection string → store it in Key Vault (Step 2).
3. **Add destination** → **Eventhouse** (create `pp_hot` if needed) → table `pp_telemetry_raw`.
4. **Publish** the Eventstream.

## Step 5 — Verify data flow (2 min)

The Function App polls BAP APIs on a timer. To verify immediately:

```powershell
# Check function execution in App Insights
az monitor app-insights query -a <appInsightsName> -g rg-pp-telemetry-lab `
  --analytics-query "traces | where timestamp > ago(15m) | where message has 'Published' | project timestamp, message | take 10"
```

Or query your Eventhouse directly:

```kusto
pp_telemetry_raw
| where ingestion_time() > ago(30m)
| project eventType, timestamp, ingestion_time()
| order by ingestion_time() desc
| take 10
```

You should see `pp.environment.lifecycle` and `pp.tenant.licenseUsage` events.

## What just happened?

```
Power Platform BAP APIs
        │
        ▼
Azure Function (.NET 8)  ──► Event Hubs (via Fabric Eventstream custom endpoint)
                                      │
                                      ▼
                              Fabric Eventstream
                                      │
                              ┌───────┴───────┐
                              ▼               ▼
                         Eventhouse       Lakehouse
                         (KQL hot)        (Bronze Delta)
```

The Function App polls Power Platform REST APIs every 15 minutes (license usage) and hourly (environment lifecycle), wraps the responses in a standard envelope (`{ eventType, timestamp, data }`), and publishes them to the Fabric Eventstream via its Event Hubs-compatible endpoint.

## Next steps

- **Full lab**: [lab/](../lab/) — adds medallion notebooks, Direct Lake BI, CI/CD
- **Add your vertical**: Copy [docs/verticals/_template.md](../docs/verticals/_template.md) and add Tier-3 KPIs
- **Business context**: [docs/business-use-case.md](../docs/business-use-case.md) — full persona definitions and KPI catalog
