# Vertical lens — Manufacturing

Discrete + process manufacturing, automotive, aerospace, supply chain.

## 1. Regulatory drivers

| Regulation | Scope | Implication |
|---|---|---|
| **ITAR / EAR** (US) | Export control | Apps handling controlled tech data tagged + access-restricted. |
| **ISO 9001 / IATF 16949** | Quality management | Apps in quality workflows have controlled change records. |
| **ISO 27001 / NIST 800-171** | Info security | Inventory + risk classification for all apps. |
| **GDPR / CCPA** | Worker personal data | Standard. |
| **CSRD / SEC climate** | Sustainability | Carbon KPI feeds Scope 2 reporting. |
| **OT/IT convergence (IEC 62443)** | Plant floor | Apps bridging OT to IT segregated; flows monitored. |

## 2. Tier-3 KPIs

| KPI | Definition | Source |
|---|---|---|
| **Shop-floor app uptime** | % of plant-tagged apps available during shift hours | App Insights availability + plant calendar |
| **OEE-app correlation** | Coefficient of variation between plant OEE and Power Apps usage on that line | Plant OEE feed + sessions |
| **EDI flow success rate** | % of B2B EDI flows completing without error | Flow runs filtered by EDI connector |
| **ITAR asset exposure** | Apps tagged `itar=true` accessed by users without active export-control clearance | CoE Kit + HR clearance feed |
| **Engineering change leadtime** | Hours from ECR submission flow start to PLM commit | Flow run + PLM webhook |

## 3. Data tags / classifications

| Tag | Values | Applied to |
|---|---|---|
| `plant_id` | plant code | `dim_app`, `dim_environment` |
| `ot_it_zone` | `it`, `dmz`, `ot_l3`, `ot_l2` | `dim_app`, `dim_environment` |
| `export_control` | `none`, `ear`, `itar` | `dim_app`, `dim_dataverse_table` |
| `quality_relevance` | `qms`, `process`, `none` | `dim_flow` |

## 4. Alert thresholds

| Signal | Threshold | Routing |
|---|---|---|
| Plant-tagged app down during shift | Immediate | Teams → Plant IT on-call |
| ITAR-tagged app accessed by non-cleared user | Immediate | PagerDuty Sec + HR |
| EDI flow failure | Within 15 min | ServiceNow → Supply chain ops |
| Shop-floor app session length drops > 50% week-over-week | Daily | Plant manager email |
| Cross-zone (OT → IT) flow created without security review | Immediate | Teams → OT Sec board |

## 5. DAX measures

```dax
Plant App Uptime % =
DIVIDE(
    CALCULATE(SUM(fact_app_availability[seconds_up]), dim_app[plant_id] <> BLANK()),
    CALCULATE(SUM(fact_app_availability[seconds_total]), dim_app[plant_id] <> BLANK())
)
EDI Success Rate =
DIVIDE(
    CALCULATE([Flow Runs], dim_flow[uses_edi_connector] = TRUE(), fact_flow_run[status] = "Succeeded"),
    CALCULATE([Flow Runs], dim_flow[uses_edi_connector] = TRUE())
)
ITAR Exposure Events =
CALCULATE(
    COUNTROWS(fact_app_session),
    dim_app[export_control] = "itar",
    fact_app_session[user_clearance] <> "active"
)
```

## 6. Lab variation

- Lab step 1: separate App Insights resources per plant region for data residency and incident isolation.
- Lab step 1: deploy Bicep with **paired-region** Event Hubs + ZRS storage (plants run 24/7).
- Add an Azure Function timer that pulls plant OEE from your historian (PI / Aveva / Ignition) and lands it in Bronze for correlation.
- Add a `dim_clearance` table from HR for ITAR enforcement.

## 7. Open questions for adopters

- What is your plant master, and is plant_id present in app context?
- Where do OT/IT zone boundaries sit in your network model? PPAOI tags must reconcile.
- Which historian feeds OEE, and what is its access model?
- Do any plants operate in air-gapped tenants? Plan a separate PPAOI deployment per tenant; aggregate via export.
