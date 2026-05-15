# Entra ID App Registration for Power Platform BAP APIs

This guide walks through creating the service principal that the Azure Function uses to authenticate against the **Power Platform BAP REST APIs** (`https://api.bap.microsoft.com`).

---

## Why you need this

The Azure Function polls tenant-level Power Platform analytics (license usage, environment lifecycle) that are **not** available via diagnostic settings. These APIs require an Entra ID service principal registered as a **Power Platform management application**.

---

## Step 1 — Register the application

1. Go to [Azure Portal → Microsoft Entra ID → App registrations](https://portal.azure.com/#view/Microsoft_AAD_IAM/ActiveDirectoryMenuBlade/~/RegisteredApps).
2. Click **+ New registration**.
3. Fill in:

   | Field | Value |
   |---|---|
   | **Name** | `pp-telemetry-lab-sp` |
   | **Supported account types** | Accounts in this organizational directory only (Single tenant) |
   | **Redirect URI** | Leave blank (not needed for daemon/service apps) |

4. Click **Register**.
5. On the **Overview** page, note:
   - **Application (client) ID** → you'll use this as `PP_CLIENT_ID`
   - **Directory (tenant) ID** → you'll use this as `PP_TENANT_ID`

---

## Step 2 — Add API permissions

1. In the app registration blade, click **API permissions** → **+ Add a permission**.
2. Select the **APIs my organization uses** tab.
3. Search for `PowerPlatform` (or `https://api.powerplatform.com`).
4. Select **Power Platform API**.
5. Choose **Delegated permissions** → check `User.Read` (or `user_impersonation`).
6. Click **Add permissions**.
7. Click **Grant admin consent for \<your tenant\>** → **Yes**.

> **Note**: For the BAP admin APIs specifically, the API permission alone is not sufficient. You must also register the app as a management application (Step 4).

---

## Step 3 — Create a client secret

1. In the app registration, go to **Certificates & secrets**.
2. Click **+ New client secret**.
3. Fill in:

   | Field | Value |
   |---|---|
   | **Description** | `pp-telemetry-lab` |
   | **Expires** | 12 months (or your org's policy) |

4. Click **Add**.
5. **Copy the secret value immediately** — it's shown only once.
6. Store it in Key Vault:

   ```powershell
   az keyvault secret set `
     --vault-name "<your-key-vault-name>" `
     --name "pp-tenant-sp-secret" `
     --value "<paste-secret-value>"
   ```

---

## Step 4 — Register as a Power Platform management application

This is the critical step that grants the service principal permission to call the BAP admin REST APIs.

### Prerequisites

- The caller must be a **Power Platform admin** or **Global admin**.
- Install the Power Apps Administration PowerShell module:

  ```powershell
  Install-Module -Name Microsoft.PowerApps.Administration.PowerShell -Scope CurrentUser -Force
  ```

### Register

```powershell
# Sign in with a Power Platform admin account
Add-PowerAppsAccount

# Register the app
New-PowerAppManagementApp -ApplicationId "<your-client-id>"
```

### Verify

```powershell
Get-PowerAppManagementApp | Where-Object { $_.ApplicationId -eq "<your-client-id>" }
```

You should see your app ID in the list.

---

## Step 5 — Test the authentication

Verify the service principal can obtain a token and call the BAP API:

```powershell
# Get a token
$body = @{
    grant_type    = "client_credentials"
    client_id     = "<your-client-id>"
    client_secret = "<your-client-secret>"
    scope         = "https://api.powerplatform.com/.default"
}

$token = (Invoke-RestMethod `
    -Method Post `
    -Uri "https://login.microsoftonline.com/<your-tenant-id>/oauth2/v2.0/token" `
    -Body $body).access_token

# Call the environments list API
$headers = @{ Authorization = "Bearer $token" }
$envs = Invoke-RestMethod `
    -Uri "https://api.bap.microsoft.com/providers/Microsoft.BusinessAppPlatform/scopes/admin/environments?api-version=2023-06-01" `
    -Headers $headers

Write-Host "Found $($envs.value.Count) environments"
```

---

## Troubleshooting

| Issue | Cause | Fix |
|---|---|---|
| `New-PowerAppManagementApp` returns **403** | Caller is not a Power Platform admin | Sign in with a Global Admin or Power Platform Admin account |
| Token request returns **AADSTS700016** | App registration not found in the tenant | Verify the client ID and tenant ID match |
| BAP API returns **401 Unauthorized** | App not registered as management app | Re-run `New-PowerAppManagementApp` |
| BAP API returns **403 Forbidden** | Token scope is wrong | Use `https://api.powerplatform.com/.default` (not `https://service.powerapps.com/`) |
| Secret expired | Client secret past expiry date | Rotate in Entra ID, update Key Vault secret |

---

## Security best practices

- **Rotate secrets** before expiry — set a calendar reminder or use Key Vault expiry notifications.
- **Use managed identity** where possible — the Function App uses UAMI for Key Vault and Event Hubs access; only the BAP API call requires the client secret.
- **Scope permissions narrowly** — the management app registration grants read-only admin access to BAP APIs; it does not grant write access to environments.
- **Audit regularly** — review `Get-PowerAppManagementApp` output periodically to ensure only authorized apps are registered.
