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

## Two patterns, same outcome

### Track 1 — Low-code / no-code

Use the platform's built-in plumbing:

1. **Link to Microsoft Fabric** mirrors Dataverse tables into OneLake (no ETL).
2. **Application Insights export** continuously writes Power Apps / Automate diagnostics to Log Analytics.
3. **Dataflow Gen2** in Fabric pulls Log Analytics + CoE Kit tables into a Lakehouse.
4. **Direct Lake** Power BI semantic model serves dashboards in real time.

**Pros**: zero code, fast, fully governed, low ops burden.
**Cons**: limited transformation, schema dictated by source, no custom enrichment.

### Track 2 — Pro-code

Use Azure native services for control + extensibility:

1. **Diagnostic settings** on each environment stream telemetry to **Event Hubs**.
2. An **Azure Function** polls **BAP REST APIs** for tenant-level metrics not available via diagnostics, and writes to the same hub.
3. **Eventstream** in Fabric ingests the hub into a **Bronze Lakehouse** (raw JSON).
4. A **notebook pipeline** transforms Bronze → Silver (typed Delta) → Gold (aggregated facts).
5. **Power BI Direct Lake** + **Eventhouse (KQL)** serve hot + warm queries.

**Pros**: full control, custom enrichment, deterministic schema, CI/CD via Bicep + GitHub Actions.
**Cons**: more services, more cost, requires platform engineering.

## When to pick which

| Signal | Recommendation |
|---|---|
| Need it this week, < 5 environments | Track 1 |
| Mostly BI dashboards, little transformation | Track 1 |
| Need sub-minute freshness | Track 2 (Eventstream) |
| Need to join with non-Power-Platform data | Track 2 |
| Regulated / sovereign cloud | Track 2 (control plane in your subscription) |
| Hybrid is common — many customers run Track 1 for Dataverse and Track 2 for diagnostics | Both |

## Security posture (both tracks)

- **Microsoft Entra ID** for all identities; service principal + workload identity federation for CI.
- **Managed identity** on Function App and Eventstream → no secrets.
- **Key Vault** for connection strings that must exist (RBAC mode, no access policies).
- **Microsoft Purview** for catalog + lineage across Dataverse, ADLS, OneLake.
- **Private endpoints** for Storage, Event Hubs, Key Vault in production.
