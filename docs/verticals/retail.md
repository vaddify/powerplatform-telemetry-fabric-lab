# Vertical lens — Retail & CPG

Retail chains, e-commerce, consumer packaged goods, hospitality.

## 1. Regulatory drivers

| Regulation | Scope | Implication |
|---|---|---|
| **PCI-DSS** | Card data | Apps in payment paths must be classified; DLP blocks card data in non-PCI envs. |
| **GDPR / CCPA / DPDP / LGPD** | Customer personal data | Consent + erasure flows tracked. |
| **CSRD / SEC climate** | Sustainability reporting | Carbon KPI feeds ESG report. |
| **PSD2 / strong customer auth** | EU payments | Auth callout flows monitored for SLA. |
| **State / country labor laws** | Workforce apps | Scheduling apps must respect local rules. |

## 2. Tier-3 KPIs

| KPI | Definition | Source |
|---|---|---|
| **Store-level adoption** | MAU per store / district / region | App Insights cloud_RoleName + store dim |
| **Seasonal capacity headroom** | % of premium connector quota consumed in 4-week peak window | BAP capacity API |
| **Supplier portal SLA** | % of supplier-facing flows completing within SLA | Flow run history + supplier dim |
| **Promo workflow lead time** | Hours from promo creation flow start to all-stores propagation | Custom step instrumentation |
| **Card data exposure events** | Count of flow runs handling PAN tokens outside PCI scope | DLP logs + connector tags |

## 3. Data tags / classifications

| Tag | Values | Applied to |
|---|---|---|
| `pci_scope` | `in`, `out` | `dim_app`, `dim_flow`, `dim_environment` |
| `store_id` | store code | `dim_app` (via cloud role / app context) |
| `channel` | `store`, `ecom`, `b2b`, `supplier`, `corporate` | `dim_app`, `dim_flow` |
| `season` | `peak`, `non_peak` | derived in `dim_date` |

## 4. Alert thresholds

| Signal | Threshold | Routing |
|---|---|---|
| Premium connector quota > 80% in peak season | Within 1h | Teams → Capacity owner |
| Supplier portal flow SLA breach > 5% | Within 15 min | ServiceNow → Supplier ops |
| PAN-handling flow detected outside `pci_scope=in` env | Immediate | PagerDuty Sec |
| Store-level adoption drops > 30% week-over-week | Daily digest | District manager email |

## 5. DAX measures

```dax
Store MAU =
CALCULATE(
    DISTINCTCOUNT(fact_app_session[user_id]),
    dim_app[channel] = "store",
    DATESINPERIOD(dim_date[date_key], MAX(dim_date[date_key]), -30, DAY)
)
Peak Capacity Headroom =
1 - DIVIDE(
    CALCULATE(SUM(fact_capacity[consumed]), dim_date[season] = "peak"),
    CALCULATE(SUM(fact_capacity[allocated]), dim_date[season] = "peak")
)
Supplier SLA Met % =
DIVIDE(
    CALCULATE([Flow Runs], dim_flow[channel] = "supplier", fact_flow_run[sla_met] = TRUE()),
    CALCULATE([Flow Runs], dim_flow[channel] = "supplier")
)
```

## 6. Lab variation

- Lab-01 step 5: add a `dim_store` table sourced from your retail master data (Dataverse or D365 Commerce) and join via `cloud_RoleName`.
- Lab-02 step 1: use `Standard_ZRS` storage and a paired-region failover policy — peak-season RTO is unforgiving.
- Add a Power BI **mobile layout** for district managers; the workspace app becomes a tablet experience.
- Add `notebooks/04_promo_leadtime.py` that joins promo flow telemetry with merchandising calendar.

## 7. Open questions for adopters

- Where is your store master kept, and is store_id present in app context strings?
- Do you have a separate PCI environment, or is PCI scope inferred per app?
- What is the season calendar (e.g., Black Friday / Diwali / Chinese New Year)? Drives `dim_date[season]`.
- Do supplier portals run in your tenant or partner tenants? Affects DLP and identity model.
