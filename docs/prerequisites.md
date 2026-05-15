# Prerequisites

## Identities & licensing

| Item | Required role | Notes |
|---|---|---|
| Microsoft 365 tenant | Global admin (setup) / Power Platform admin | Trial works |
| Power Platform environment | System Administrator | Managed env recommended for Track 2 |
| Dataverse database | Provisioned in target environment | Required for CoE Kit + Link to Fabric |
| Azure subscription | Contributor + User Access Administrator | Needed for RBAC assignments |
| Microsoft Fabric capacity | Capacity Admin | F2+ SKU or 60-day trial |
| Microsoft Entra ID | App registration permission | For service principal in Track 2 |

## Power Platform components

- **CoE Starter Kit** installed in a dedicated environment (latest release).
- **Power Platform Admin Center** access for tenant-level analytics + diagnostic settings.
- **Application Insights** linked to one or more environments (Track 1) — Power Platform admin → Environments → *env* → Settings → Product → Application Insights.

## Azure resources (Track 2 / pro-code)

Provisioned by [infra/bicep/main.bicep](../infra/bicep/main.bicep):

- Log Analytics workspace
- Application Insights (workspace-based)
- Storage account (ADLS Gen2, hierarchical namespace)
- Event Hubs namespace + hub `pp-telemetry`
- Function App (Flex Consumption, .NET 8 isolated)
- Key Vault (RBAC mode)
- User-assigned managed identity

## Microsoft Fabric

- A **workspace** assigned to the Fabric capacity.
- A **Lakehouse** named `pp_bronze`, `pp_silver`, `pp_gold` (created by lab steps).
- For Track 1: enable **"Link to Microsoft Fabric"** on the target Dataverse environment (Power Apps maker portal → Tables → *Analyze* → Link to Microsoft Fabric).

## Local tooling

| Tool | Version | Install |
|---|---|---|
| Azure CLI | 2.60+ | `winget install Microsoft.AzureCLI` |
| Bicep | 0.27+ | `az bicep install` |
| .NET SDK | 8.0+ | `winget install Microsoft.DotNet.SDK.8` |
| Azure Functions Core Tools | 4.x | `npm i -g azure-functions-core-tools@4` |
| Python | 3.11+ | `winget install Python.Python.3.11` |
| Node.js | 20 LTS | `winget install OpenJS.NodeJS.LTS` |
| VS Code Insiders | latest | with extensions: `hediet.vscode-drawio`, `ms-azuretools.vscode-bicep`, `ms-azuretools.vscode-azurefunctions`, `ms-python.python` |

## Network / firewall

- Outbound HTTPS to `*.powerplatform.com`, `*.dynamics.com`, `*.azure.com`, `*.fabric.microsoft.com`, `*.servicebus.windows.net`.
- If running behind a corporate proxy, configure `HTTPS_PROXY` for `az` and `func` CLIs.

## Verify

```powershell
az --version
az bicep version
func --version
dotnet --list-sdks
python --version
node --version
```
