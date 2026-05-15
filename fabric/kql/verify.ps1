$tok = az account get-access-token --resource https://trd-93ajhz73ee2pjtnbzz.z6.kusto.fabric.microsoft.com --query accessToken -o tsv
$h = @{Authorization="Bearer $tok"; "Content-Type"="application/json"}
$q = "https://trd-93ajhz73ee2pjtnbzz.z6.kusto.fabric.microsoft.com/v1/rest/query"

Write-Host "=== ROW COUNTS ==="
foreach($tbl in @("pp_telemetry_raw","environments","license_usage")) {
    $r = Invoke-RestMethod -Method Post -Uri $q -Headers $h -Body (@{db="pp_hot";csl="$tbl | count"} | ConvertTo-Json)
    Write-Host "  $tbl : $($r.Tables[0].Rows[0]) rows"
}

Write-Host "`n=== environments table ==="
$r = Invoke-RestMethod -Method Post -Uri $q -Headers $h -Body (@{db="pp_hot";csl="environments | project envName, displayName, environmentSku, provisioningState, location, mgmtState, runtimeState"} | ConvertTo-Json)
Write-Host "  Columns: $($r.Tables[0].Columns.ColumnName -join ', ')"
$r.Tables[0].Rows | ForEach-Object { Write-Host "  $($_ -join ' | ')" }

Write-Host "`n=== environment_inventory (gold) ==="
$r = Invoke-RestMethod -Method Post -Uri $q -Headers $h -Body (@{db="pp_hot";csl="environment_inventory | project envName, displayName, environmentSku, provisioningState, location"} | ConvertTo-Json)
$r.Tables[0].Rows | ForEach-Object { Write-Host "  $($_ -join ' | ')" }

Write-Host "`n=== TABLES LIST ==="
$m = "https://trd-93ajhz73ee2pjtnbzz.z6.kusto.fabric.microsoft.com/v1/rest/mgmt"
$r = Invoke-RestMethod -Method Post -Uri $m -Headers $h -Body (@{db="pp_hot";csl=".show tables"} | ConvertTo-Json)
$r.Tables[0].Rows | ForEach-Object { Write-Host "  $($_[0])" }

Write-Host "`n=== UPDATE POLICIES ==="
$r = Invoke-RestMethod -Method Post -Uri $m -Headers $h -Body (@{db="pp_hot";csl=".show table environments policy update"} | ConvertTo-Json)
$r.Tables[0].Rows | ForEach-Object { Write-Host "  $($_ -join ' | ')" }
