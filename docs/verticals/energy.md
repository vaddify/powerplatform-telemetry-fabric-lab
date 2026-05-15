# Vertical lens — Energy & Utilities

Oil & gas (upstream / midstream / downstream), electric utilities, gas utilities, water, renewables.

## 1. Regulatory drivers

| Regulation | Scope | Implication |
|---|---|---|
| **NERC CIP** (NA bulk power) | Critical electric infrastructure | BES Cyber System–touching apps tagged + access logged. |
| **TSA Pipeline Security Directives** | US pipelines | Incident reporting timelines. |
| **NIS2** (EU) | Essential services | OT/IT incident reporting. |
| **REMIT** (EU energy markets) | Trading | Same drivers as Financial Services for trading desks. |
| **EPA / state environmental** | Emissions reporting | Apps in EHS workflows have controlled record retention. |
| **CSRD / SEC climate** | ESG | Carbon KPI feeds Scope 1/2/3 reporting. |

## 2. Tier-3 KPIs

| KPI | Definition | Source |
|---|---|---|
| **Field-worker app uptime** | % availability of mobile field apps in service hours | App Insights availability + crew calendar |
| **NERC-CIP asset exposure** | Apps tagged `nerc_cip=true` accessed by users without active CIP-004 training | CoE Kit + training feed |
| **Outage-response flow leadtime** | Hours from outage event to crew dispatch flow completion | Flow runs + outage management system |
| **Asset-data lineage coverage** | % of asset-related apps with full Purview lineage | Purview API |
| **Emissions per workload** | Estimated kgCO₂e per Power Platform workload, attributed to asset | Azure Carbon API + workload-asset map |

## 3. Data tags / classifications

| Tag | Values | Applied to |
|---|---|---|
| `nerc_cip` | `bes_high`, `bes_medium`, `bes_low`, `none` | `dim_app`, `dim_flow`, `dim_environment` |
| `asset_class` | `well`, `pipeline`, `substation`, `feeder`, `meter`, `wind_turbine`, `solar_array`, `none` | `dim_app`, `dim_flow` |
| `business_unit` | `upstream`, `midstream`, `downstream`, `t&d`, `retail`, `trading`, `corporate` | `dim_app` |
| `region` | regulatory region | `dim_environment` |

## 4. Alert thresholds

| Signal | Threshold | Routing |
|---|---|---|
| NERC-CIP app accessed by user without current CIP-004 | Immediate | PagerDuty Sec + CIP compliance |
| Field-worker app uptime < 99% in service window | Within 15 min | NOC pager |
| Outage-response flow leadtime > target | Immediate | T&D control room |
| Asset-data lineage broken | Daily | Data steward email |
| Cross-region data movement on regulated asset | Immediate | Teams → Compliance |

## 5. DAX measures

```dax
NERC CIP Apps = CALCULATE(DISTINCTCOUNT(dim_app[app_id]), dim_app[nerc_cip] <> "none")
NERC CIP Exposure 7D =
CALCULATE(
    COUNTROWS(fact_app_session),
    dim_app[nerc_cip] <> "none",
    fact_app_session[user_cip004_active] = FALSE(),
    DATESINPERIOD(dim_date[date_key], MAX(dim_date[date_key]), -7, DAY)
)
Field App Service-Hour Uptime =
CALCULATE(
    [Plant App Uptime %],   -- reuse manufacturing measure pattern
    dim_app[asset_class] <> "none",
    dim_date[is_service_hour] = TRUE()
)
Outage Response Mean Leadtime (h) =
AVERAGEX(
    FILTER(fact_flow_run, dim_flow[outage_response] = TRUE()),
    fact_flow_run[duration_seconds] / 3600
)
```

## 6. Lab variation

- Lab-02 step 1: Bicep parameterized for **paired-region** Event Hubs and ZRS storage; many utilities require in-region only.
- Add an Azure Function or Logic App to pull asset master and outage events from your OMS / GIS into Bronze.
- Add a Purview scan rule for asset-data lineage as part of the lab-02 pipeline.
- Add a `notebooks/04_carbon_attribution.py` that joins Azure Carbon Optimization data with `dim_app[asset_class]` for ESG attribution.

## 7. Open questions for adopters

- What is your asset master (SAP PM, Maximo, GE APM, OSIsoft AF), and how is `asset_id` propagated into app context?
- Which environments are CIP-classified, and what is the access-control model (training feed source)?
- Which OMS feeds outage events, and over what API?
- Do you operate in air-gapped OT networks? Plan a separate constrained PPAOI deployment per network.
