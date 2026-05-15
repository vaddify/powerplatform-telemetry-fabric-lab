# Vertical lens — Healthcare & Life Sciences

Providers, payers, pharma, medtech, CROs.

## 1. Regulatory drivers

| Regulation | Scope | Implication |
|---|---|---|
| **HIPAA** (US) | PHI handling | All PHI-touching apps need BAA-covered data flow; access logs retained 6 years. |
| **HITECH** | Breach notification | Detection + reporting clock starts at incident; PPAOI must surface incidents fast. |
| **21 CFR Part 11** (FDA) | E-signatures, GxP records | Audit trail integrity, time sync, signature manifest on flows used in clinical/manufacturing. |
| **GDPR / UK DPA** | EU/UK personal data | Subject rights flow to gold lakehouse. |
| **HDS** (France) | Hosting health data | Region/sovereignty tag on environments. |
| **NHS DSPT** (UK) | NHS data | Annual toolkit attestation; PPAOI provides evidence pack. |

## 2. Tier-3 KPIs

| KPI | Definition | Source |
|---|---|---|
| **PHI-touching asset count** | Apps + flows tagged `phi=true` with current owner | CoE Kit + tag table |
| **PHI access events** | Dataverse audit events on PHI tables, by user and BU | Dataverse audit |
| **Copilot transcripts redaction rate** | % of Copilot Studio messages where PII/PHI was successfully redacted | Custom redaction service log → Bronze |
| **GxP flow signature coverage** | % of GxP-tagged flow runs with valid e-signature manifest | Flow run history + Part 11 service |
| **Region drift** | Count of assets created in non-approved region for HDS / data residency | Environment lifecycle events |

## 3. Data tags / classifications

| Tag | Values | Applied to |
|---|---|---|
| `phi` | `true`, `false` | `dim_app`, `dim_flow`, `dim_dataverse_table` |
| `gxp_relevance` | `gxp`, `non_gxp` | `dim_flow` |
| `data_residency` | `us`, `eu`, `uk`, `apac`, `restricted` | `dim_environment` |
| `consent_basis` | `treatment`, `research`, `operations`, `marketing`, `none` | `dim_dataverse_table` |

## 4. Alert thresholds

| Signal | Threshold | Routing |
|---|---|---|
| New PHI-tagged app without BAA-validated connector | Immediate | Teams → Privacy Officer |
| Bulk export from PHI table (> 1k rows / hour) | Immediate | PagerDuty Sec |
| GxP flow run without signature manifest | Immediate | ServiceNow Quality ticket |
| Region drift detected | Immediate | Teams → Architecture board |
| Copilot redaction rate < 99.5% over 24h | Within 1h | Teams → Copilot owner |

## 5. DAX measures

```dax
PHI Assets = CALCULATE(DISTINCTCOUNT(dim_app[app_id]), dim_app[phi] = TRUE())
PHI Access 7D =
CALCULATE(
    COUNTROWS(fact_dataverse_event),
    dim_dataverse_table[phi] = TRUE(),
    DATESINPERIOD(dim_date[date_key], MAX(dim_date[date_key]), -7, DAY)
)
Copilot Redaction Rate =
DIVIDE(
    CALCULATE(COUNTROWS(fact_copilot_message), fact_copilot_message[redaction_success] = TRUE()),
    COUNTROWS(fact_copilot_message)
)
GxP Signed Run Rate =
DIVIDE(
    CALCULATE([Flow Runs], dim_flow[gxp_relevance] = "gxp", fact_flow_run[signature_valid] = TRUE()),
    CALCULATE([Flow Runs], dim_flow[gxp_relevance] = "gxp")
)
```

## 6. Lab variation

- Lab-01 step 1: link App Insights only to environments in approved regions; check `data_residency` before connecting.
- Lab-02 step 5: add an Eventstream **transformation** that calls a Functions endpoint to redact PII/PHI before landing in Bronze.
- Add a `notebooks/04_signature_attestation.py` notebook that hashes each GxP flow run output and writes a manifest table.
- Power BI report: add a "Privacy Cockpit" page; quarterly exports for HIPAA OCR readiness.

## 7. Open questions for adopters

- Are you a Covered Entity, Business Associate, or both? This drives BAA scope on connectors.
- Where is your master patient/subject ID kept, and how is it joined to telemetry safely (hashed)?
- Which environments are GxP-validated? Validation freeze rules apply to Bicep changes.
- Do you need 21 CFR Part 11–compliant audit storage (WORM)? Use ADLS immutable blob policies.
