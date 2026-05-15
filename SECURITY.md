# Security Policy

## Reporting a vulnerability

If you discover a security vulnerability in this project, please report it responsibly:

1. **Do not** open a public GitHub issue.
2. Email the maintainers at the address listed in the repo's security tab, or use [GitHub's private vulnerability reporting](https://docs.github.com/en/code-security/security-advisories/guidance-on-reporting-and-writing/privately-reporting-a-security-vulnerability).
3. Include a description, reproduction steps, and the potential impact.

We will acknowledge receipt within 48 hours and aim to release a fix within 7 days for critical issues.

## Security design

This project follows security best practices:

| Principle | Implementation |
|---|---|
| **No secrets in code** | All secrets stored in Azure Key Vault; Function App reads via managed identity + KV references. |
| **Managed Identity** | User-Assigned Managed Identity (UAMI) for Function App ↔ Key Vault, Storage, and Event Hubs. |
| **RBAC over access policies** | Key Vault uses RBAC mode; no legacy access policies. |
| **OIDC for CI/CD** | GitHub Actions authenticates to Azure via workload identity federation — no stored credentials. |
| **Least privilege** | Each role assignment is scoped to the specific resource, not the resource group. |
| **No PII in telemetry** | The pipeline captures platform operational metrics; PII redaction is configurable per vertical. |

## .gitignore protections

The following are excluded from version control:

- `local.settings.json` — local development secrets
- `*.env` / `*.pem` / `*.pfx` — credential files
- `main.json` — compiled ARM template (regenerate from Bicep)
- `secrets.json` — any local secret store

## Dependency management

- NuGet packages are pinned to specific versions in `PpTelemetryForwarder.csproj`.
- Review Dependabot alerts (enable in repo settings) for known vulnerabilities.

## Supported versions

| Version | Supported |
|---|---|
| main (latest) | Yes |
| Older commits | Best effort |
