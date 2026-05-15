# Architecture overview

## The problem

Power Platform emits operational signals across many surfaces:

- **Power Apps** — session telemetry, control errors, performance traces (Application Insights).
- **Power Automate** — cloud flow runs, action latency, failures (Dataverse + AI).
- **Copilot Studio** — conversation transcripts, message metrics, agent activity.
- **Dataverse** — entity changes, plug-in execution, audit logs.
- **CoE Kit** — inventory of apps, flows, makers, environments.
- **Tenant analytics** — usage, adoption, license consumption (Power Platform admin center / BAP REST APIs).

Each surface has its own retention window (often 7–30 days). To do **historical** trend analysis, capacity planning, ML on usage, or cross-surface correlation, you need to **land all of it in one analytical store**. Microsoft Fabric (OneLake + Lakehouse + Direct Lake) is the strategic landing zone.

## How it works

This lab uses Azure-native services for full control, custom enrichment, and CI/CD:

1. **Diagnostic settings** on each environment stream telemetry to **Event Hubs**.
2. An **Azure Function** (.NET 8 isolated, Flex Consumption) polls **BAP REST APIs** for tenant-level metrics not available via diagnostics (license usage, environment lifecycle), and writes to the same hub.
3. **Eventstream** in Fabric ingests the hub into a **Bronze Lakehouse** (raw JSON).
4. A **notebook pipeline** transforms Bronze → Silver (typed Delta) → Gold (aggregated star schema).
5. **Power BI Direct Lake** serves warm analytics; **Eventhouse (KQL)** serves a hot 7-day window for sub-second incident queries.

**Why this approach**: full control over schema and enrichment, deterministic transforms, CI/CD via Bicep + GitHub Actions, and all infrastructure in your own Azure subscription (critical for regulated / sovereign environments).

## Security posture

- **Microsoft Entra ID** for all identities; service principal + workload identity federation for CI.
- **Managed identity** on Function App and Eventstream — no secrets in app settings.
- **Key Vault** for connection strings that must exist (RBAC mode, no access policies).
- **Microsoft Purview** for catalog + lineage across Dataverse, ADLS, OneLake.
- **Private endpoints** for Storage, Event Hubs, Key Vault in production.
