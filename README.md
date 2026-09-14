# Protect360 AI

Customer 360 and Next Best Action platform built on Snowflake.

## Architecture

- **Bronze** — Raw ingestion layer (VARIANT payloads)
- **Silver** — Cleaned, typed, and enriched tables
- **Gold** — Customer 360 profiles, NBA recommendations, action catalogue
- **ML** — Model metadata and scoring outputs
- **Governance** — Pipeline runs, data quality results, Cortex AI audit

## Streamlit App

5-page dashboard in `app/streamlit_app.py`:
1. Executive Overview — KPIs, top actions, high-priority customers
2. Customer 360 Profile — Search, filter, and inspect any customer
3. Risk & Propensity — ML model scores and factor explanations
4. Next Best Action — Ranked actions with accept/modify/reject workflow
5. Governance Monitor — DQ, consent rates, model coverage

## RBAC Roles

| Role | Access |
|---|---|
| P360_ADMIN | Full control |
| P360_ENGINEER | Read/write Bronze, Silver, Gold, ML |
| P360_ML_ENGINEER | Read Silver/Gold, read/write ML |
| P360_APP_USER | Read Gold only |
| P360_ADVISOR | Read Gold (region-filtered) |
| P360_SUPPORT_REVIEWER | Read Gold + Governance |
| P360_GOVERNANCE | Read Governance + Gold |

## Setup

Run DDL scripts in order:
1. `ddl/01_database_and_schemas.sql`
2. `ddl/02_warehouses.sql`
3. `ddl/03_roles_and_grants.sql`

Then deploy `app/streamlit_app.py` to a Snowflake workspace.
