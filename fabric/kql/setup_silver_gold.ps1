param([string]$KustoCluster = "https://trd-93ajhz73ee2pjtnbzz.z6.kusto.fabric.microsoft.com")

$tok = az account get-access-token --resource $KustoCluster --query accessToken -o tsv
$hdr = @{Authorization="Bearer $tok"; "Content-Type"="application/json"}
$mgmt = "$KustoCluster/v1/rest/mgmt"
$db = "pp_hot"

function Invoke-KQL {
    param([string]$Csl, [string]$Label)
    try {
        $body = @{db=$db; csl=$Csl} | ConvertTo-Json -Depth 5
        $r = Invoke-RestMethod -Method Post -Uri $mgmt -Headers $hdr -Body $body
        Write-Host "[OK]  $Label"
        return $r
    } catch {
        $resp = $_.Exception.Response
        if ($resp) {
            $sr = New-Object IO.StreamReader($resp.GetResponseStream())
            $errBody = $sr.ReadToEnd()
            Write-Host "[FAIL] $Label"
            Write-Host "       $errBody" | Select-Object -First 3
        } else {
            Write-Host "[FAIL] $Label - $_"
        }
        return $null
    }
}

Write-Host "=== SILVER TABLES ==="

Invoke-KQL -Label "environments table" -Csl @"
.create-merge table environments (
    timestamp: datetime,
    envName: string,
    location: string,
    displayName: string,
    environmentSku: string,
    provisioningState: string,
    tenantId: string,
    instanceUrl: string,
    version: string,
    mgmtState: string,
    runtimeState: string
)
"@

Invoke-KQL -Label "license_usage table" -Csl @"
.create-merge table license_usage (
    timestamp: datetime,
    tenantId: string,
    licenseData: dynamic
)
"@

Write-Host "`n=== TRANSFORM FUNCTIONS ==="

Invoke-KQL -Label "fn_expand_environments" -Csl @"
.create-or-alter function fn_expand_environments() {
    pp_telemetry_raw
    | where eventType == "pp.environment.lifecycle"
    | mv-expand env = data.value
    | project
        timestamp,
        envName            = tostring(env.name),
        location           = tostring(env.location),
        displayName        = tostring(env.properties.displayName),
        environmentSku     = tostring(env.properties.environmentSku),
        provisioningState  = tostring(env.properties.provisioningState),
        tenantId           = tostring(env.properties.tenantId),
        instanceUrl        = tostring(env.properties.linkedEnvironmentMetadata.instanceUrl),
        version            = tostring(env.properties.linkedEnvironmentMetadata.version),
        mgmtState          = tostring(env.properties.states.management.id),
        runtimeState       = tostring(env.properties.states.runtime.id)
}
"@

Invoke-KQL -Label "fn_expand_license_usage" -Csl @"
.create-or-alter function fn_expand_license_usage() {
    pp_telemetry_raw
    | where eventType == "pp.tenant.licenseUsage"
    | project
        timestamp,
        tenantId    = tostring(data.tenantId),
        licenseData = data.value
}
"@

Write-Host "`n=== UPDATE POLICIES ==="

Invoke-KQL -Label "environments update policy" -Csl @"
.alter table environments policy update @'[{"IsEnabled": true, "Source": "pp_telemetry_raw", "Query": "fn_expand_environments()", "IsTransactional": true, "PropagateIngestionProperties": false}]'
"@

Invoke-KQL -Label "license_usage update policy" -Csl @"
.alter table license_usage policy update @'[{"IsEnabled": true, "Source": "pp_telemetry_raw", "Query": "fn_expand_license_usage()", "IsTransactional": true, "PropagateIngestionProperties": false}]'
"@

Write-Host "`n=== GOLD VIEW: environment_inventory (latest state per env) ==="

Invoke-KQL -Label "environment_inventory view" -Csl @"
.create-or-alter materialized-view environment_inventory on table environments {
    environments
    | summarize arg_max(timestamp, *) by envName
}
"@

Write-Host "`n=== VERIFY ==="

$r = Invoke-KQL -Label "query environments" -Csl "environments | count"
if ($r) { Write-Host "       environments rows: $($r.Tables[0].Rows[0])" }

$r = Invoke-KQL -Label "query license_usage" -Csl "license_usage | count"
if ($r) { Write-Host "       license_usage rows: $($r.Tables[0].Rows[0])" }

$r = Invoke-KQL -Label "query environment_inventory" -Csl "environment_inventory | count"
if ($r) { Write-Host "       environment_inventory rows: $($r.Tables[0].Rows[0])" }

$r = Invoke-KQL -Label "query environment_inventory data" -Csl "environment_inventory | project envName, displayName, environmentSku, provisioningState, location"
if ($r) { $r.Tables[0].Rows | ForEach-Object { Write-Host "       $($_ -join ' | ')" } }

Write-Host "`n=== DONE ==="
