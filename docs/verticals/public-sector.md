# Vertical lens — Public Sector

US federal, state/local, education, defense, civilian agencies, EU/UK government.

## 1. Regulatory drivers

| Regulation | Scope | Implication |
|---|---|---|
| **FedRAMP High / Moderate** (US) | Federal cloud workloads | PPAOI deployed in GCC High / DoD; sovereign control plane. |
| **DoD IL4 / IL5** | Defense data | Tenant + region tagging mandatory. |
| **CJIS** | Criminal justice info | Apps touching CJIS data segregated; access logs 3y. |
| **StateRAMP / TX-RAMP / etc.** | State authorizations | Similar to FedRAMP, state scope. |
| **FERPA** | Education records | Student data tagged + access-controlled. |
| **Section 508 / WCAG 2.2 AA** | Accessibility | All apps tested; PPAOI tracks coverage. |
| **FOIA / public records** | Civic transparency | Asset registry exportable for FOIA response. |
| **NIS2 / Cyber Resilience Act** (EU) | Operational resilience | Incident reporting timelines. |

## 2. Tier-3 KPIs

| KPI | Definition | Source |
|---|---|---|
| **Boundary integrity** | Count of assets created outside the authorized boundary (region/tenant/SKU) | Environment lifecycle events |
| **Accessibility coverage** | % of public-facing apps with passing WCAG 2.2 scan in last 90 days | Accessibility Insights / custom scan service |
| **FOIA registry freshness** | Days since last refresh of the FOIA asset registry | CoE Kit + custom registry |
| **CJIS access events** | Audit count on CJIS-tagged tables | Dataverse audit |
| **Mission-critical app SLA** | % uptime per mission-criticality tier | App Insights availability |

## 3. Data tags / classifications

| Tag | Values | Applied to |
|---|---|---|
| `boundary` | `il2`, `il4`, `il5`, `gcch`, `commercial` | `dim_environment`, `dim_app` |
| `cjis` | `true`, `false` | `dim_dataverse_table`, `dim_app` |
| `accessibility_scope` | `public`, `internal`, `exempt` | `dim_app` |
| `mission_tier` | `t1_mission_critical`, `t2_essential`, `t3_admin` | `dim_app`, `dim_flow` |
| `foia_in_scope` | `true`, `false` | `dim_app`, `dim_flow` |

## 4. Alert thresholds

| Signal | Threshold | Routing |
|---|---|---|
| Asset created outside authorized boundary | Immediate | Teams → ATO/A&A team |
| WCAG scan fails on public app | Immediate | Teams → Accessibility lead |
| CJIS access by user without active certification | Immediate | PagerDuty Sec |
| T1 mission-critical app uptime < 99.9% (rolling 30d) | Within 1h | NOC pager |
| FOIA registry stale > 7 days | Daily | Records officer email |

## 5. DAX measures

```dax
Boundary Drift Events 30D =
CALCULATE(
    COUNTROWS(fact_env_event),
    fact_env_event[event_type] = "asset_created",
    NOT(dim_environment[boundary] IN { "il5", "gcch" })
)
WCAG Coverage % =
DIVIDE(
    CALCULATE(DISTINCTCOUNT(dim_app[app_id]),
              dim_app[accessibility_scope] = "public",
              dim_app[wcag_pass_date] >= TODAY() - 90),
    CALCULATE(DISTINCTCOUNT(dim_app[app_id]), dim_app[accessibility_scope] = "public")
)
T1 Uptime =
DIVIDE(
    CALCULATE(SUM(fact_app_availability[seconds_up]), dim_app[mission_tier] = "t1_mission_critical"),
    CALCULATE(SUM(fact_app_availability[seconds_total]), dim_app[mission_tier] = "t1_mission_critical")
)
```

## 6. Lab variation

- Use **Microsoft Cloud for Sovereignty** / **GCC High** subscriptions; Bicep parameterized for sovereign endpoints.
- Lab GitHub Actions: use **GitHub Actions for Azure Government** runners; OIDC issuer URL is the sovereign one.
- Add a `notebooks/04_accessibility_scan.py` notebook that calls Accessibility Insights CLI on each public app's URL and writes results.
- Add a Power BI export job that produces the FOIA registry as CSV nightly to a SharePoint records library.

## 7. Open questions for adopters

- Which sovereign cloud (GCC, GCC High, DoD, Azure Government secret)? Pipeline must respect endpoints + identity.
- Who is your Authorizing Official (AO), and what is the ATO boundary diagram? Map to `dim_environment[boundary]`.
- Which app tier requires Continuous Monitoring (ConMon) deliverables? PPAOI can produce them automatically.
- Do you have a Records Management policy that obliges WORM storage for telemetry? Use immutable blob policies.
