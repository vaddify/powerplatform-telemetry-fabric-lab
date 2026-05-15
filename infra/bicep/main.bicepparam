using './main.bicep'

param prefix = 'pptel'
param location = 'eastus2'
// Replace with your Entra ID object ID:  az ad signed-in-user show --query id -o tsv
param adminPrincipalId = 'e316b80d-3d64-437d-a9ec-a08a2685b5fd'
