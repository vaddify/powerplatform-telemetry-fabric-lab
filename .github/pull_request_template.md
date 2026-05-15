## Summary

<!-- Brief description of changes -->

## Type of change

- [ ] Bug fix
- [ ] New vertical lens
- [ ] New KPI / DAX measure
- [ ] Pipeline / infrastructure change
- [ ] Documentation update

## Checklist

- [ ] No secrets, connection strings, or tenant-specific GUIDs committed
- [ ] `.gitignore` covers any new build artifacts or local configs
- [ ] Bicep validates: `az bicep build --file infra/bicep/main.bicep`
- [ ] Function builds: `dotnet build` (no errors)
- [ ] If adding a KPI: documented in both vertical `.md` and `measures.dax`
- [ ] Lab steps reference correct relative paths
- [ ] Tier-1/Tier-2 measures are unchanged (verticals add, never replace)

## Related issues

<!-- Closes #XX -->
