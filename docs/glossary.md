# Glossary

| Term | Meaning |
|---|---|
| **BAP** | Business Application Platform — the REST API surface for Power Platform admin operations (`api.bap.microsoft.com`). |
| **CoE Kit** | Center of Excellence Starter Kit — Microsoft-published solution that inventories Power Platform assets in Dataverse. |
| **Dataverse** | Managed relational store underpinning Power Platform; tables, relationships, security roles. |
| **Direct Lake** | Power BI semantic model mode that reads Delta tables in OneLake without import or DirectQuery latency. |
| **Eventhouse** | Fabric KQL database, successor to Azure Data Explorer for real-time analytics inside Fabric. |
| **Eventstream** | Fabric no-code pipeline that ingests streaming sources (Event Hubs, Kafka, custom apps) into a Lakehouse or Eventhouse. |
| **Lakehouse** | Fabric item combining a managed Delta table store + a files area, queryable by Spark and SQL endpoint. |
| **Link to Microsoft Fabric** | Native Dataverse feature that mirrors selected tables to a Fabric workspace as Delta tables in OneLake; no ETL. |
| **Medallion (Bronze/Silver/Gold)** | Common Lakehouse layering: raw → cleaned/typed → business-ready aggregates. |
| **OneLake** | Single SaaS-managed data lake shared by all Fabric items in a tenant. |
| **Workload identity federation** | Lets GitHub Actions authenticate to Azure as a service principal without a secret. |
