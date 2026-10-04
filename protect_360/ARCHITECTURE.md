# Protect360 AI - Architecture & Data Flow

## Overview

Protect360 AI is a **Customer 360 and Next Best Action (NBA) platform** for an Australian health insurance provider, built on Snowflake. It ingests raw customer, policy, claims, and interaction data through a medallion architecture (Bronze → Silver → Gold), applies ML risk models and an AI sentiment pipeline, computes next-best-action recommendations, and surfaces everything through a 5-page Streamlit-in-Snowflake advisor dashboard.

---

## System Architecture

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                          Snowsight (Browser)                                │
│  ┌───────────────────────────────────────────────────────────────────────┐  │
│  │                  Streamlit Frontend (SiS)                             │  │
│  │                                                                       │  │
│  │  ┌─────────────────────┐  ┌──────────────────────────────────────┐   │  │
│  │  │    Sidebar Nav       │  │  5 Pages:                            │   │  │
│  │  │                      │  │  1. Executive Overview                │   │  │
│  │  │  Executive Overview  │  │  2. Customer 360 Profile             │   │  │
│  │  │  Customer 360        │  │  3. Risk & Propensity                │   │  │
│  │  │  Risk & Propensity   │  │  4. Next Best Action                 │   │  │
│  │  │  Next Best Action    │  │  5. Governance Monitor               │   │  │
│  │  │  Governance Monitor  │  │                                      │   │  │
│  │  └─────────────────────┘  └──────────────────────────────────────┘   │  │
│  └───────────────────────────────┬───────────────────────────────────────┘  │
│                                  │ st.connection("snowflake")               │
│                                  ▼                                          │
│  ┌───────────────────────────────────────────────────────────────────────┐  │
│  │                        Snowflake (APP_WH)                             │  │
│  │                                                                       │  │
│  │  ┌─────────┐    ┌─────────┐    ┌─────────┐    ┌─────────┐           │  │
│  │  │ BRONZE  │ →  │ SILVER  │ →  │  GOLD   │ ←  │   ML    │           │  │
│  │  │ (raw)   │    │ (clean) │    │ (C360)  │    │(scores) │           │  │
│  │  └─────────┘    └─────────┘    └─────────┘    └─────────┘           │  │
│  │       ↑                             │                                 │  │
│  │   Seed data                    4 Secure Views                         │  │
│  │   (Python gen)                 + Semantic View                        │  │
│  └───────────────────────────────────────────────────────────────────────┘  │
└─────────────────────────────────────────────────────────────────────────────┘
```

### Runtime Configuration

| Component              | Value                          |
|------------------------|--------------------------------|
| Database               | `PROTECT360_DB`                |
| Admin role             | `P360_ADMIN`                   |
| Query warehouse (app)  | `APP_WH`                       |
| Transform warehouse    | `TRANSFORM_WH`                 |
| Ingest warehouse       | `INGEST_WH`                    |
| Compute pool           | `SYSTEM_COMPUTE_POOL_CPU`      |
| Streamlit version      | `>= 1.54.0`                   |
| Python version         | `>= 3.11`                     |
| Theme primary color    | `#FFCC00` (gold)               |

### File Structure

```
protect360-app/                        # Streamlit application
├── .streamlit/config.toml             # Theme configuration
├── pyproject.toml                     # Python dependencies
├── snowflake.yml                      # SiS deployment definition
└── streamlit_app.py                   # Dashboard app (~670 lines)

cortex_project/                        # Cortex Analyst semantic model
├── cortex-project.yaml                # Project manifest
└── PROTECT360_CUSTOMER_360.sv.yaml    # Semantic view definition

(workspace root)
├── bronze_tables.sql                  # Bronze table DDL (alternate schema)
├── bronze_layer_tables.sql            # Bronze raw table DDL (primary)
├── bronze_seed_data.sql               # Generated synthetic INSERT statements
├── generate_bronze_data.py            # Python seed data generator
├── load_bronze_data.py                # Snowpark loader for seed data
└── gold_semantic_views.sql            # Gold secure view definitions
```

---

## Medallion Architecture

### Bronze Layer — `PROTECT360_DB.BRONZE`

Raw data ingested from source systems. All tables store a `RAW_PAYLOAD` (VARIANT) alongside typed columns for lineage and deduplication.

| # | Table                     | Rows  | Source System   | Description                           |
|---|---------------------------|-------|-----------------|---------------------------------------|
| 1 | `CUSTOMER_RAW`            | ~1005 | CRM             | Customer demographics and consent     |
| 2 | `POLICY_RAW`              | ~var  | POLICY_ADMIN    | Policy details, premiums, renewals    |
| 3 | `CLAIM_RAW`               | ~var  | CLAIMS_ENGINE   | Claims history (hospital, dental, etc)|
| 4 | `FINANCIAL_PROFILE_RAW`   | ~var  | FINANCE_SYS     | Income band, capacity score, assets   |
| 5 | `INTERACTION_RAW`         | ~var  | CONTACT_CENTRE  | Call/chat/email transcripts           |
| 6 | `HOSPITALIZATION_RAW`     | ~var  | CLAIMS_ENGINE   | Hospital admission records            |
| 7 | `DIGITAL_EVENT_RAW`       | ~var  | WEB_ANALYTICS   | Clickstream (quotes, page views)      |
| 8 | `QUOTE_RAW`               | ~var  | QUOTE_ENGINE    | Quote attempts and abandonments       |
| 9 | `POSTCODE_ENRICHMENT_RAW` | ~var  | ABS             | Socioeconomic decile by postcode      |

Each row includes:
- `SOURCE_SYSTEM_CODE` — origin system
- `SOURCE_RECORD_ID` — natural key from source
- `BATCH_ID` — ingestion batch identifier
- `RECORD_HASH` — MD5 of source record ID for dedup
- `INGESTED_AT` — timestamp of ingestion

Data quality defects are intentionally seeded: 5 duplicate customers, 10 null renewal dates on ACTIVE policies, 5 empty transcripts, 3 `UNKNOWN` income bands.

### Silver Layer — `PROTECT360_DB.SILVER`

Cleaned, typed, and enriched data. Key table:

| Table                        | Description                                          |
|------------------------------|------------------------------------------------------|
| `INTERACTION_AI_SIGNAL`      | AI-processed interaction signals with sentiment       |
|                              | (`SENTIMENT_LABEL`, `SENTIMENT_SCORE`, `PROCESSED_TS`)|

### Gold Layer — `PROTECT360_DB.GOLD`

Business-ready tables and views that power the dashboard.

#### Core Tables

| Table                      | Description                                              |
|----------------------------|----------------------------------------------------------|
| `CUSTOMER_360_PROFILE`     | One row per customer — master C360 fact table             |
| `NEXT_BEST_ACTION`         | Ranked NBA recommendations per customer                  |
| `NBA_ACTION_CATALOG`       | Reference table of all possible actions                  |
| `NBA_ACTION_CANDIDATE`     | Full candidate set before suppression filtering          |
| `ACTION_OUTCOME`           | Advisor decisions (ACCEPTED / REJECTED / MODIFIED)       |

#### Secure Views

| View                            | Purpose                                                |
|---------------------------------|--------------------------------------------------------|
| `VW_EXECUTIVE_OVERVIEW`         | Aggregated KPIs — no customer PII                      |
| `VW_ADVISOR_CUSTOMER_360`       | Customer-level C360 + risk + top NBA + sentiment       |
| `VW_HIGH_PRIORITY_CUSTOMERS`    | Urgent action list with urgency tiers (1-5)            |
| `VW_GOVERNANCE_MONITOR`         | DQ pass rates, consent rates, coverage metrics         |

### ML Layer — `PROTECT360_DB.ML`

| Table                | Description                                           |
|----------------------|-------------------------------------------------------|
| `DIM_MODEL`          | Model registry (MDL001–MDL003)                        |
| `MODEL_SCORE`        | Per-customer scores with `SCORE_CLASS` (HIGH/MED/LOW) |
| `MODEL_SCORE_FACTOR` | Explainable factors per score (SHAP-style)            |

**Models:**

| Key     | Model Name                      | Purpose                      |
|---------|---------------------------------|------------------------------|
| MDL001  | Vulnerability and Needs Score   | Health risk assessment        |
| MDL002  | Government Scheme Eligibility   | Lapse risk prediction         |
| MDL003  | Gig Worker Needs Score          | Product propensity scoring    |

---

## Data Model — Gold Layer Relationships

```
                    ┌─────────────────────────────┐
                    │    CUSTOMER_360_PROFILE      │
                    │─────────────────────────────│
                    │ CUSTOMER_SK (PK)             │ ← MD5(CUSTOMER_ID)
                    │ CUSTOMER_ID                  │
                    │ FULL_NAME, AGE, AGE_BAND     │
                    │ GENDER, STATE_CODE, POSTCODE  │
                    │ CUSTOMER_STATUS               │
                    │ MARKETING_CONSENT_FLAG         │
                    │ HEALTH_DATA_CONSENT_FLAG       │
                    │ ACTIVE/LAPSED_POLICY_COUNT     │
                    │ TOTAL_ANNUAL_PREMIUM           │
                    │ NEXT_RENEWAL_DATE              │
                    │ COVERAGE_GAP_DAYS              │
                    │ HAS_HEALTH_POLICY_FLAG         │
                    │ PROTECTION_GAP_FLAG            │
                    │ CLAIM_COUNT_3Y/12M             │
                    │ HOSPITALIZATION_COUNT_3Y        │
                    │ QUOTE_ATTEMPTS/ABANDONED_6M     │
                    │ INCOME_BAND, CAPACITY_SCORE     │
                    │ SOCIOECONOMIC_DECILE            │
                    │ DATA_COMPLETENESS_SCORE         │
                    │ DATA_QUALITY_STATUS             │
                    │ EMPLOYMENT_TYPE_CODE             │
                    │ ITR_FILING_FLAG, IS_UNINSURED    │
                    │ SEGMENT_TYPE                     │
                    └──────────┬──────────────────────┘
                               │ CUSTOMER_SK
             ┌─────────────────┼──────────────────┐
             │                 │                   │
    ┌────────▼────────┐ ┌─────▼───────────┐ ┌────▼──────────────┐
    │  MODEL_SCORE     │ │ NEXT_BEST_ACTION│ │  ACTION_OUTCOME   │
    │─────────────────│ │─────────────────│ │──────────────────│
    │ MODEL_SCORE_SK   │ │ NEXT_BEST_      │ │ ACTION_OUTCOME_SK │
    │ CUSTOMER_KEY(FK) │ │   ACTION_SK     │ │ NEXT_BEST_ACTION  │
    │ MODEL_KEY (FK)   │ │ CUSTOMER_KEY(FK)│ │   _SK (FK)        │
    │ SCORE            │ │ ACTION_KEY (FK) │ │ CUSTOMER_KEY (FK) │
    │ SCORE_CLASS      │ │ PRIORITY_RANK   │ │ ADVISOR_DECISION  │
    │ CURRENT_SCORE_   │ │ FINAL_ACTION_   │ │ ADVISOR_FEEDBACK  │
    │   FLAG           │ │   SCORE         │ │ OUTCOME_RECORDED  │
    └────────┬────────┘ │ RECOMMENDED_     │ │   _TS             │
             │          │   CHANNEL        │ │ FOLLOW_UP_        │
    ┌────────▼────────┐ │ REASON_TEXT      │ │   REQUIRED        │
    │ MODEL_SCORE_    │ │ ADVISOR_MESSAGE  │ └───────────────────┘
    │   FACTOR        │ │ ACTION_EXPIRY_TS │
    │─────────────────│ │ HUMAN_REVIEW_    │
    │ MODEL_SCORE_SK  │ │   REQUIRED       │
    │   (FK)          │ └─────┬───────────┘
    │ FACTOR_NAME     │       │ ACTION_KEY
    │ FACTOR_VALUE    │ ┌─────▼───────────┐
    │ CONTRIBUTION    │ │NBA_ACTION_CATALOG│
    │ DIRECTION       │ │─────────────────│
    │ FACTOR_RANK     │ │ ACTION_KEY (PK)  │
    │ EXPLANATION     │ │ ACTION_NAME      │
    └─────────────────┘ │ ACTION_CATEGORY  │
                        └─────────────────┘
    ┌─────────────────┐
    │DIM_MODEL         │      ┌────────────────────┐
    │─────────────────│      │NBA_ACTION_CANDIDATE │
    │ MODEL_KEY (PK)   │      │────────────────────│
    │ MODEL_NAME       │      │ CUSTOMER_KEY (FK)   │
    └─────────────────┘      │ ACTION_KEY (FK)     │
                              │ ELIGIBLE_FLAG       │
                              │ SUPPRESSION_REASON  │
                              │ FINAL_ACTION_SCORE  │
                              └────────────────────┘
```

---

## Data Flow

### 1. Data Generation & Ingestion

```
generate_bronze_data.py          load_bronze_data.py
       │                                │
       │  Generates ~1000+              │  Reads /tmp/bronze_seed_data.sql
       │  customers + related           │  Executes INSERT batches via
       │  entities as SQL               │  Snowpark session.sql()
       │                                │
       ▼                                ▼
/tmp/bronze_seed_data.sql  →  PROTECT360_DB.BRONZE.*_RAW tables
                                        │
                           ┌────────────┼─────────────────────┐
                           │            │                      │
                     CUSTOMER_RAW  POLICY_RAW  CLAIM_RAW  ... (9 tables)
```

### 2. Medallion Transformation

```
BRONZE (Raw)                SILVER (Cleaned)              GOLD (Business-ready)
─────────────              ─────────────────              ────────────────────

CUSTOMER_RAW ─────────┐
POLICY_RAW ───────────┤
CLAIM_RAW ────────────┤
FINANCIAL_PROFILE_RAW ┼──→  (cleaning & typing)  ──→  CUSTOMER_360_PROFILE
HOSPITALIZATION_RAW ──┤                                      │
QUOTE_RAW ────────────┤                               (one row per customer,
POSTCODE_ENRICHMENT ──┘                                all domains merged)

INTERACTION_RAW ──→  INTERACTION_AI_SIGNAL ──→  (sentiment joins into
                     (AI sentiment extraction)    VW_ADVISOR_CUSTOMER_360)
```

### 3. ML Scoring Pipeline

```
CUSTOMER_360_PROFILE
         │
         ▼
   ┌───────────────────────────────────────┐
   │         3 ML Models                    │
   │                                        │
   │  MDL001: Health Risk / Vulnerability   │
   │  MDL002: Lapse Risk / Govt Scheme      │
   │  MDL003: Product Propensity / Gig      │
   │                                        │
   │  Output: SCORE (0.0–1.0)              │
   │          SCORE_CLASS (HIGH/MED/LOW)    │
   │          FACTOR explanations           │
   └───────────────┬───────────────────────┘
                   │
                   ▼
       ML.MODEL_SCORE + ML.MODEL_SCORE_FACTOR
```

### 4. Next Best Action Engine

```
CUSTOMER_360_PROFILE + MODEL_SCORE
         │
         ▼
┌─────────────────────────────────────────┐
│         NBA Decision Engine              │
│                                          │
│  1. Evaluate all actions from catalog    │
│  2. Check eligibility rules              │
│  3. Apply suppression filters:           │
│     - NO_CONSENT (no marketing consent)  │
│     - NOT_ELIGIBLE (criteria not met)    │
│  4. Score eligible actions               │
│  5. Rank by FINAL_ACTION_SCORE           │
│  6. Flag HUMAN_REVIEW_REQUIRED           │
└───────────────┬─────────────────────────┘
                │
                ▼
   NBA_ACTION_CANDIDATE (full set, with reasons)
                │
                ▼
   NEXT_BEST_ACTION (eligible, ranked)
                │
         ┌──────┴──────┐
         │  Action     │
         │  Categories │
         ├─────────────┤
         │ INSURANCE   │  (policy-related actions)
         │ COMMUNITY   │  (CSR, financial counselling)
         │ EDUCATION   │  (awareness, wellness programs)
         └─────────────┘
```

### 5. Advisor Decision Loop (Write Path)

```
Advisor views NBA recommendations on Page 4
         │
         ├──→ ✅ Accept  ──→  INSERT ACTION_OUTCOME (ACCEPTED, follow_up=FALSE)
         │
         ├──→ ❌ Reject  ──→  INSERT ACTION_OUTCOME (REJECTED, follow_up=TRUE)
         │
         └──→ ✏️ Modify  ──→  Show all eligible candidates
                    │
                    └──→  Confirm  ──→  INSERT ACTION_OUTCOME (MODIFIED, follow_up=TRUE)
                                        (records original NBA_SK + advisor feedback)

After any decision:
  - Clear selected customer from session state
  - Redirect to Customer 360 Profile for next customer
  - Decision appears in Governance Monitor
```

---

## Dashboard Pages

### Page 1: Executive Overview

Reads `VW_EXECUTIVE_OVERVIEW` for aggregated KPIs (no PII). Shows:
- Total customers, protection gap %, high vulnerability count, DQ pass rate
- Top rank-1 NBA actions (bar chart)
- High-priority customers by state (bar chart)
- Top 10 vulnerable (Tier 1) and top 10 critical (near-retirement ITR filers)

### Page 2: Customer 360 Profile

Reads `VW_ADVISOR_CUSTOMER_360` with filters (search, state, age band, NBA status). Separates pending vs actioned customers. On row selection, shows full profile: identity, policy, risk scores, data quality progress bar.

### Page 3: Risk & Propensity

Reads model scores and `MODEL_SCORE_FACTOR` for the selected customer. Shows vulnerability score, top action score, and explainable factors per model (contribution values, direction arrows, explanations). Conditionally shows Gig Worker model based on employment type and income band.

### Page 4: Next Best Action

Reads `NEXT_BEST_ACTION` joined with `NBA_ACTION_CATALOG`. Displays ranked action cards with score, channel, category, reason, advisor message, and expiry. Rank-1 card has Accept/Reject/Modify buttons. Modify mode shows all `NBA_ACTION_CANDIDATE` rows with eligibility status and suppression reasons.

### Page 5: Governance Monitor

Reads `VW_GOVERNANCE_MONITOR` and supplementary queries. Shows:
- DQ pass rate, marketing consent rate, ML score coverage (metrics)
- Data quality distribution (donut chart: GREEN/AMBER/RED)
- NBA decision outcomes (donut chart: ACCEPTED/REJECTED/MODIFIED)
- Consent rates breakdown (donut chart)
- Recent advisor decisions table (last 20)
- Model score coverage by model and class

---

## Semantic View (Cortex Analyst)

Deployed to `PROTECT360_DB.GOLD.PROTECT360_CUSTOMER_360`.

Exposes 4 base tables to Cortex Analyst:

| Semantic Table                  | Source View/Table                  | Primary Key    |
|---------------------------------|------------------------------------|----------------|
| `VW_ADVISOR_CUSTOMER_360`       | `GOLD.VW_ADVISOR_CUSTOMER_360`     | `CUSTOMER_ID`  |
| `VW_HIGH_PRIORITY_CUSTOMERS`    | `GOLD.VW_HIGH_PRIORITY_CUSTOMERS`  | `CUSTOMER_ID`  |
| `VW_EXECUTIVE_OVERVIEW`         | `GOLD.VW_EXECUTIVE_OVERVIEW`       | (single row)   |
| `VW_GOVERNANCE_MONITOR`         | `GOLD.VW_GOVERNANCE_MONITOR`       | (single row)   |

**Verified Queries:**
1. "Who are the highest risk customers?" — filters by HIGH health/lapse risk class
2. "How many customers have a protection gap?" — COUNT where PROTECTION_GAP_FLAG = TRUE
3. "Which customers have renewals overdue or due within 30 days?" — DAYS_TO_RENEWAL BETWEEN -30 AND 0
4. "Which customers have negative sentiment and medium to high lapse risk?" — joins sentiment + lapse class

---

## Urgency Tiers (VW_HIGH_PRIORITY_CUSTOMERS)

| Tier | Criteria                                                  |
|------|-----------------------------------------------------------|
| 1    | Protection gap AND coverage gap > 365 days (CRITICAL)     |
| 2    | Lapse risk score > 0.6                                    |
| 3    | Protection gap (any duration)                             |
| 4    | Age >= 60 AND LOW income band                             |
| 5    | Multiple risk factors (catch-all)                         |

---

## Key Design Decisions

1. **Medallion architecture** — Bronze stores raw VARIANT payloads for full lineage; Silver applies AI enrichment; Gold materializes business-ready profiles and views.

2. **Secure views** — All Gold views are `SECURE VIEW`, ensuring data access follows Snowflake's secure view semantics (no query plan leakage).

3. **ML explainability** — Each model score stores ranked factors with contribution values and human-readable explanations, enabling advisors to understand *why* a score is high.

4. **NBA suppression transparency** — The full candidate set (`NBA_ACTION_CANDIDATE`) is preserved with suppression reason codes, so the UI can explain *why* no actions are available.

5. **Human-in-the-loop** — Advisors can accept, reject, or modify recommendations. Decisions are recorded in `ACTION_OUTCOME` and tracked on the Governance Monitor.

6. **Consent-gated actions** — Insurance and education actions require marketing consent. Community referrals are evaluated independently but still check eligibility criteria.

7. **Data quality monitoring** — Every profile carries a `DATA_COMPLETENESS_SCORE` (0-100%) and `DATA_QUALITY_STATUS` (PASS/WARN/FAIL), surfaced both per-customer and in aggregate governance metrics.

8. **Intentional DQ defects** — Seed data includes duplicates, nulls, empty transcripts, and unknown income bands to exercise the quality monitoring pipeline.

9. **Gig Worker model gating** — The Gig Worker Needs Score factors are only shown when the customer's employment type is GIG_WORKER/DAILY_WAGE and income band is not ABOVE_10L.

10. **Session state navigation** — Customer selection on Page 2 carries through to Pages 3-4 via `st.session_state`. After a decision, the advisor is redirected back to Page 2 to pick the next customer.
