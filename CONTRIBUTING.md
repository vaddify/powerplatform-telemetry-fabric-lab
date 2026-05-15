# Contributing to PPAOI

Thank you for your interest in improving the Power Platform Adoption & Operations Intelligence lab!

## Core principle

> **Verticals add, never replace.** Tier-1 and Tier-2 KPIs stay identical across all forks so cross-org benchmarks remain comparable. Tier-3 KPIs are scoped to `docs/verticals/<industry>.md` and a labeled section in `notebooks/measures.dax`.

## How to contribute

### Bug reports & feature requests

1. Open an [Issue](../../issues) describing the problem or idea.
2. Include the track (low-code / pro-code), Azure region, and Fabric SKU if relevant.

### Adding a new vertical

1. Copy `docs/verticals/_template.md` to `docs/verticals/<your-vertical>.md`.
2. Fill in all seven sections: regulations, Tier-3 KPIs, tags, alerts, DAX measures, lab variation, open questions.
3. Add your Tier-3 DAX measures to `notebooks/measures.dax` under a clearly labeled section header (e.g., `// === Tier 3 — Aerospace ===`).
4. Submit a PR.

### Code changes

1. Fork the repo and create a feature branch (`feature/my-change`).
2. Make your changes. Ensure:
   - **Bicep** templates pass `az bicep build` without errors.
   - **C# function** builds with `dotnet build` (no warnings as errors).
   - **Notebooks** are idempotent (re-runnable without duplicating data).
3. Test locally using `func start` for the Azure Function.
4. Submit a PR against `main`.

### PR checklist

- [ ] No secrets, connection strings, or tenant-specific GUIDs in committed files.
- [ ] `.gitignore` covers any new build artifact or local config.
- [ ] If adding a KPI, it is documented in both the vertical markdown and `measures.dax`.
- [ ] Lab steps reference the correct relative paths.

## Development setup

See [docs/prerequisites.md](./docs/prerequisites.md) for required tooling.

Quick summary:

```powershell
# Build the function
cd src/functions/PpTelemetryForwarder
dotnet build

# Validate Bicep
az bicep build --file infra/bicep/main.bicep

# Run function locally (requires local.settings.json)
func start
```

## Code of conduct

This project follows the [Microsoft Open Source Code of Conduct](https://opensource.microsoft.com/codeofconduct/). By participating, you agree to abide by its terms.

## License

By contributing, you agree that your contributions will be licensed under [MIT](./LICENSE).
