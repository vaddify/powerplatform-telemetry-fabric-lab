# Vertical lens — Financial Services

Banking, capital markets, insurance, wealth management.

## 1. Regulatory drivers

| Regulation | Scope | Implication for Power Platform telemetry |
|---|---|---|
| **SOX** (US) | Public companies — financial reporting controls | Apps/flows touching the GL or sub-ledger systems are in scope; need change history, owner, approver. |
| **MAR** (EU) / market abuse | Trading workflows | Surveillance on flows that move trade or position data; full audit trail. |
| **PCI-DSS** | Card data | Apps handling PAN must be classified; DLP must block external connectors. |
| **GDPR / CCPA / DPDP** | Personal data | Right-to-erasure must propagate from Dataverse to gold lakehouse. |
| **DORA** (EU) | Operational resilience | ICT incident logging; concentration risk on critical Power Platform workloads. |
| **FFIEC, OCC, Basel III ops risk** | Banking | Inventory of all material apps with risk rating; recovery plans. |

## 2. Tier-3 KPIs

| KPI | Definition | Data source |
|---|---|---|
| **SOX-relevant app count** | Apps tagged `sox=true` with current owner + last attestation date | CoE Kit + custom tag table |
| **Segregation-of-Duties violations** | Flows where the same maker is creator + sole approver | Flow definitions JSON |
| **High-risk connector exposure** | Flows in Production using SQL/HTTP/custom connectors against trading or GL systems | DLP logs + flow connector inventory |
| **Mean time to attest** | Days between asset creation and first compliance attestation | Custom attestation table in Dataverse |
| **Trade data egress events** | Count of flows exporting trade/position data outside the trust boundary | Eventhouse on `pp_hot` |

## 3. Data tags / classifications

| Tag | Values | Applied to |
|---|---|---|
| `sox_relevance` | `in_scope`, `out_of_scope`, `pending_review` | `dim_app`, `dim_flow` |
| `data_classification` | `public`, `internal`, `confidential`, `mnpi`, `pci` | `dim_app`, `dim_flow`, `dim_dataverse_table` |
| `system_of_record` | `gl`, `subledger`, `oms`, `crm`, `none` | `dim_flow` |
| `attestation_status` | `attested`, `expired`, `never` | `dim_app`, `dim_flow` |

## 4. Alert thresholds

| Signal | Threshold | Routing |
|---|---|---|
| New flow with high-risk connector in Prod | Immediate | Teams → 2nd-line risk; ServiceNow Sec ticket |
| SoD violation detected | Immediate | Teams → CoE Lead + maker's manager |
| SOX-tagged app without attestation | > 90 days | Email digest weekly |
| Unowned SOX-tagged app | Immediate | Teams → Compliance Lead |
| MNPI-tagged data leaving Dataverse via flow | Immediate | PagerDuty Sec on-call |

## 5. DAX measures

```dax
SOX Apps Active = CALCULATE(DISTINCTCOUNT(dim_app[app_id]), dim_app[sox_relevance] = "in_scope")
SOX Apps Unattested = CALCULATE([SOX Apps Active], dim_app[attestation_status] <> "attested")
SoD Violations 30D =
CALCULATE(
    DISTINCTCOUNT(dim_flow[flow_id]),
    dim_flow[creator_id] = dim_flow[approver_id],
    DATESINPERIOD(dim_date[date_key], MAX(dim_date[date_key]), -30, DAY)
)
High Risk Connector Exposure =
CALCULATE(
    DISTINCTCOUNT(dim_flow[flow_id]),
    dim_flow[uses_high_risk_connector] = TRUE(),
    dim_environment[environment_type] = "Production"
)
```

## 6. Lab variation

- Add a **second DLP policy** in lab step 4: `Block all custom + HTTP connectors in Production unless app is tagged sox=true and attested`.
- Add a **Purview classification rule** for MNPI in lab step 4 (Eventstream → on Bronze write, run Purview scan).
- Extend `02_silver_to_gold.py` to read an external `attestations` Dataverse table and join to `dim_app`.
- Power BI report: add an "Attestation Cockpit" page; export to PDF on a monthly schedule for audit evidence.

## 7. Open questions for adopters

- Who owns the attestation workflow (CoE, Risk, Internal Audit)?
- What is the system-of-record list to which `dim_flow.system_of_record` must reconcile?
- What MNPI/MAR detection rules exist already in your SIEM that PPAOI should *complement* (not duplicate)?
- Is your tenant a sovereign / dedicated cloud (e.g., Microsoft Cloud for Sovereignty)?
