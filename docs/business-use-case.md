# Business Use Case — Power Platform Adoption & Operations Intelligence (PPAOI)

> A vertical-agnostic blueprint for any organization to govern, fund, and scale its Power Platform estate using historical telemetry landed in Microsoft Fabric.

---

## 1. Problem statement (CoE-led)

Every Center of Excellence (CoE) running Power Platform at scale faces the same operational gap:

> *Telemetry is scattered across Application Insights, Dataverse, the CoE Kit, the Power Platform Admin Center, and the BAP REST APIs. Each source has its own retention window (often 7–30 days), its own schema, and its own access model. The CoE cannot answer basic governance questions across time, environments, and business units without manually stitching exports together every reporting cycle.*

The CoE is accountable for three things — and is structurally under-equipped to deliver any of them without a unified historical store:

1. **Govern** the estate (policy, security, compliance, lifecycle).
2. **Operate** the estate (reliability, capacity, cost, support).
3. **Grow** the estate (adoption, maker enablement, business value).

PPAOI gives the CoE one analytical store — Microsoft Fabric — that powers all three responsibilities, with a Power BI workspace app that any persona (Platform Owner, Sponsor, Risk Officer, Maker Lead) can consume.

## 2. Primary persona — the CoE

| Sub-persona | Owns | Asks |
|---|---|---|
| **CoE Lead / Platform Owner** | The platform as a service | "Is the estate healthy, growing, and within risk appetite?" |
| **Governance & Compliance Lead** | Policy, DLP, audit | "Where is my exposure? What changed last quarter?" |
| **Maker Enablement Lead** | Training, Champions program | "Who is shipping value, who is stuck, who needs coaching?" |
| **Operations / SRE for Power Platform** | Capacity, reliability, support | "What is breaking, what is throttling, what is costing me?" |

## 3. Secondary personas (consume the same dataset)

| Persona | Question | View |
|---|---|---|
| **Business Unit Sponsor** | "Is my Power Platform investment paying off?" | BU-scoped Adoption + Value report |
| **Risk / Compliance Officer** | "Are my regulated workloads correctly classified and audited?" | Risk Posture + Audit report |
| **Finance / FinOps** | "What is my cost-to-serve per BU and per workload?" | Cost & Capacity report |
| **Maker / Citizen Developer** | "How are my apps doing? Are there errors I should fix?" | Self-service maker portal in Power BI |

## 4. Outcomes & KPIs

The base set is **eight vertical-agnostic KPIs** every CoE tracks. Each one is materialized as a measure on the Fabric `pp_gold` semantic model.

### Tier 1 — the original five (mandatory)

| # | KPI | Definition | Where it comes from |
|---|---|---|---|
| 1 | **Adoption Index** | MAU ÷ licensed users, trended monthly | App Insights sessions + license inventory |
| 2 | **Maker Productivity** | Apps + flows shipped per maker per quarter; lead time from create → publish | CoE Kit `admin_app`, `admin_flow` |
| 3 | **Reliability** | Error rate %, p95 flow duration, SLA breaches | App Insights exceptions, flow runs |
| 4 | **Cost-to-Serve** | Capacity consumption (premium connectors, AI Builder credits, Dataverse storage) per BU | BAP capacity APIs, Dataverse metrics |
| 5 | **Risk Posture** | % apps without owner, % flows with high-impact connectors, orphaned assets, policy violations | CoE Kit + DLP policy logs |

### Tier 2 — industry-standard additions (recommended)

| # | KPI | Definition | Why it matters |
|---|---|---|---|
| 6 | **Security & Compliance Posture** | DLP policy violations, connector risk classification, environment isolation breaches, audit-log completeness | Required by every regulated vertical; complements Risk by separating *security operations* from *governance hygiene* |
| 7 | **Business Value Realized** | Hours saved per flow (configurable rate × runs × baseline), ROI, value pipeline | The number that justifies CoE budget; standard ask from CFO/COO |
| 8 | **Sustainability (Carbon)** | Estimated kgCO₂e per workload from Azure Carbon Optimization + Fabric capacity emissions | Increasingly mandated (CSRD, SEC climate rules); easy to expose, hard to retrofit later |

> Verticals can extend this list (see `docs/verticals/*.md`). They should not remove Tier 1 or Tier 2 measures so cross-org benchmarks remain comparable.

## 5. Scope

### In scope (v1)

- Sources: Power Apps (canvas + model-driven), Power Automate (cloud flows), Copilot Studio, Dataverse audit + activity, CoE Starter Kit, Power Platform Admin Center analytics, BAP REST APIs (license, capacity, environment lifecycle), DLP policy logs.
- Pipeline: Diagnostic settings + Application Insights + Link to Microsoft Fabric → Microsoft Fabric (Bronze/Silver/Gold lakehouse, Eventstream for streaming, Eventhouse for hot KQL).
- Delivery: Power BI Direct Lake workspace app with a base report per persona; alerting via Teams + email; data exfiltration to ServiceNow / Jira optional.

### Out of scope (v1, parked as v2 backlog)

- Microsoft 365 Copilot adoption (separate Microsoft Graph data product).
- Dynamics 365 first-party app telemetry.
- Custom connector deep tracing.
- ML-based anomaly detection on session/flow patterns.
- Cross-tenant rollups (MSP scenarios).

## 6. Success criteria

The deployment is successful when the CoE can answer **all 12 of these questions in under 30 seconds** using the Power BI workspace app, with data no older than 24 hours:

1. How many MAU did each environment have last month, year-over-year?
2. Which 10 apps had the highest error rate last week?
3. Which makers shipped the most apps/flows last quarter? Which shipped none?
4. What is the projected Dataverse storage exhaustion date per environment?
5. How many flows reference a high-impact connector (e.g., SQL, HTTP, custom) in a non-Production environment?
6. How many apps have no owner or an inactive owner?
7. What did each BU consume in premium connector requests vs their allocation?
8. Which environments breached a DLP policy in the last 30 days, and who acted on it?
9. What is the estimated ROI (hours saved × labor rate) of the top 20 flows?
10. What is the estimated kgCO₂e of the platform last month per BU?
11. Which Copilot Studio agents have rising escalation rates?
12. Which historical incidents (from ServiceNow) correlate with a release of a Power Platform asset?

## 7. Customization surface (what each vertical changes)

```
docs/verticals/<vertical>.md         <- KPIs + thresholds + glossary delta
notebooks/02_silver_to_gold.py       <- add dim/fact for vertical-specific tags
notebooks/measures.dax               <- add vertical KPI measures
infra/bicep/main.bicepparam          <- region, retention, SKU, sovereignty
lab-0X-<vertical>/README.md          <- optional vertical lab on top of base two
.github/workflows/*.yml              <- add policy gates (e.g., Purview scan)
```

The base pipeline, schema, and Tier 1+2 measures stay identical. Verticals **add**, never **replace**.

## 8. Vertical lenses

| Vertical | Specialization (summary) | Detailed stub |
|---|---|---|
| Financial Services | SOX/MAR app classification, segregation-of-duties on flows, 7y audit retention | [verticals/financial-services.md](./verticals/financial-services.md) |
| Healthcare & Life Sciences | HIPAA/PHI tag, Copilot transcript redaction, 21 CFR Part 11 e-sig | [verticals/healthcare.md](./verticals/healthcare.md) |
| Retail & CPG | Store-level adoption, seasonal capacity forecasting, supplier portal SLAs | [verticals/retail.md](./verticals/retail.md) |
| Manufacturing | OT/IT app inventory, shop-floor downtime correlation, EDI flow monitoring | [verticals/manufacturing.md](./verticals/manufacturing.md) |
| Public Sector | FedRAMP/IL boundary tagging, FOIA registry, WCAG accessibility coverage | [verticals/public-sector.md](./verticals/public-sector.md) |
| Energy & Utilities | Field-worker app uptime, NERC CIP-tagged flows, asset-data lineage | [verticals/energy.md](./verticals/energy.md) |

## 9. Why Fabric (vs build-your-own)

| Capability | Why it matters for PPAOI |
|---|---|
| OneLake | One copy of data across Dataverse mirror, Eventstream output, notebook outputs — no movement |
| Direct Lake | Sub-second BI on the same Delta files, no import/refresh windows |
| Eventhouse (KQL) | Hot 7-day window for incident response without a second store |
| Link to Microsoft Fabric (Dataverse) | Zero-ETL CoE Kit + business data — biggest accelerator for v1 |
| Workspace + capacity governance | Maps cleanly to CoE chargeback model |
| Purview integration | Single catalog across PP, Fabric, Azure |

## 10. Adoption roadmap (90-day plan)

| Phase | Weeks | Outcome |
|---|---|---|
| **Inception** | 1–2 | Use case approved, exec sponsor signed, vertical lens picked, workspace + capacity provisioned |
| **Foundations** | 3–6 | Pipeline live: Bicep deployed, Function polling, Eventstream streaming, base Power BI report shipped |
| **Industrialization** | 7–10 | Gold layer + DQ checks running, CI/CD wired, alerts configured |
| **Activation** | 11–12 | Workspace app published, alerts wired, vertical KPIs added, CoE operating rhythms (weekly review) started |

## 11. Open questions for adopters (fill in your fork)

- Who is the executive sponsor and what is the funded budget code?
- Which BUs are in the v1 rollout, and which are out?
- What is the data classification of Power Platform telemetry in your org (it is rarely "public")?
- Which vertical lens applies, and which Tier-3 KPIs do you need to add?
- What is the alert routing? Teams channel? ServiceNow queue? PagerDuty?
- What is the retention policy for the gold layer? (Default: 7 years cold, 90 days hot.)
