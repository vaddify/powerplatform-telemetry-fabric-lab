<#
.SYNOPSIS
    Updates the Key Vault secret with a new Eventstream Custom Endpoint connection string
    and restarts the Function App.

.DESCRIPTION
    After recreating an eventstream or rotating keys, get the connection string from the Fabric UI:
    1. Open your Fabric workspace
    2. Open the eventstream
    3. Click the custom endpoint source node
    4. Copy the "Event Hub connection string" value
    5. Run this script with the connection string

.PARAMETER ConnectionString
    The Event Hub connection string from the Fabric Custom Endpoint source.

.PARAMETER ResourceGroup
    The Azure resource group name. Default: pp-telemetry-lab.

.PARAMETER KeyVaultName
    The Key Vault name. Required.

.PARAMETER FunctionAppName
    The Function App name. Required.

.PARAMETER WorkspaceId
    (Optional) Fabric workspace GUID — used to verify eventstream topology.

.PARAMETER EventstreamId
    (Optional) Fabric eventstream GUID — used to verify eventstream topology.
#>
param(
    [Parameter(Mandatory)]
    [string]$ConnectionString,

    [string]$ResourceGroup   = 'pp-telemetry-lab',

    [Parameter(Mandatory)]
    [string]$KeyVaultName,

    [Parameter(Mandatory)]
    [string]$FunctionAppName,

    [string]$WorkspaceId,
    [string]$EventstreamId
)

$ErrorActionPreference = 'Stop'

Write-Host "Updating Key Vault secret 'fabric-eventstream-cs'..."
az keyvault secret set --vault-name $KeyVaultName --name fabric-eventstream-cs --value $ConnectionString -o none

Write-Host "Restarting Function App to pick up new secret..."
az functionapp restart -g $ResourceGroup -n $FunctionAppName

if ($WorkspaceId -and $EventstreamId) {
    Write-Host "Verifying eventstream topology..."
    $tok = az account get-access-token --resource https://api.fabric.microsoft.com --query accessToken -o tsv
    $hdr = @{ Authorization = "Bearer $tok" }
    $def = Invoke-RestMethod -Method Post -Uri "https://api.fabric.microsoft.com/v1/workspaces/$WorkspaceId/eventstreams/$EventstreamId/getDefinition" -Headers $hdr
    $payload = ($def.definition.parts | Where-Object { $_.path -eq 'eventstream.json' }).payload
    $topo = [System.Text.Encoding]::UTF8.GetString([Convert]::FromBase64String($payload)) | ConvertFrom-Json
    Write-Host "  Sources: $($topo.sources.Count)"
    Write-Host "  Destinations: $($topo.destinations.Count)"
    $topo.destinations | ForEach-Object { Write-Host "  DEST: $($_.name) ($($_.type))" }
}

Write-Host "`nDone. Function App will start sending events to the new eventstream on next timer trigger."
