# RetireEasy - Architecture & Data Flow

## Overview

RetireEasy is a **Streamlit-in-Snowflake** application for retirement planning surveys. It collects comprehensive person profiles — personal details, financial data, health information, insurance coverage, and preferences — and persists them across a normalized set of Snowflake tables.

---

## System Architecture

```
┌──────────────────────────────────────────────────────┐
│                   Snowsight (Browser)                 │
│  ┌────────────────────────────────────────────────┐  │
│  │           Streamlit Frontend (SiS)             │  │
│  │                                                │  │
│  │  ┌──────────────┐                              │  │
│  │  │  Sidebar Nav  │  ➕ New Person Registration  │  │
│  │  └──────────────┘                              │  │
│  │                                                │  │
│  │  11 collapsible form sections (expanders)      │  │
│  │  Client-side validation (regex)                │  │
│  │  Session state for submission feedback          │  │
│  └─────────────────────┬──────────────────────────┘  │
│                        │                              │
│                        │ st.connection("snowflake")   │
│                        │ (Snowpark session)            │
│                        ▼                              │
│  ┌────────────────────────────────────────────────┐  │
│  │            Snowflake (COMPUTE_WH)              │  │
│  │                                                │  │
│  │  Database: PROTECT360_DB                       │  │
│  │  Schema:   SURVEY                              │  │
│  │                                                │  │
│  │  ┌──────────────────────────────────────────┐  │  │
│  │  │  PERSON_ID_SEQ (Sequence)                │  │  │
│  │  │  Generates RE-XXXXX identifiers          │  │  │
│  │  └──────────────────────────────────────────┘  │  │
│  │                                                │  │
│  │  ┌──────────────────────────────────────────┐  │  │
│  │  │  11 Normalized Tables                    │  │  │
│  │  │  (see Data Model below)                  │  │  │
│  │  └──────────────────────────────────────────┘  │  │
│  └────────────────────────────────────────────────┘  │
└──────────────────────────────────────────────────────┘
```

### Runtime Configuration

| Component            | Value                       |
|----------------------|-----------------------------|
| Compute pool         | `SYSTEM_COMPUTE_POOL_CPU`   |
| Query warehouse      | `COMPUTE_WH`               |
| Streamlit version    | `>= 1.54.0`                |
| Python version       | `>= 3.11`                  |
| Theme primary color  | `#FFCC00` (gold)           |

### File Structure

```
retireeasy/
├── .streamlit/
│   └── config.toml          # Theme configuration
├── pyproject.toml            # Python dependencies
├── snowflake.yml             # SiS deployment definition
└── streamlit_app.py          # Application (single-file, ~644 lines)
```

---

## Data Model

All tables live in `PROTECT360_DB.SURVEY`. Every table is keyed on `PERSON_ID` (1:1 relationship with the PERSON table).

```
                        ┌──────────────────────┐
                        │       PERSON          │
                        │──────────────────────│
                        │ PERSON_ID (PK)        │  ← RE-XXXXX from PERSON_ID_SEQ
                        │ FULL_NAME             │
                        │ DATE_OF_BIRTH         │
                        │ GENDER                │
                        │ NATIONALITY           │
                        │ MARITAL_STATUS         │
                        │ STATE_CODE            │
                        │ POSTCODE              │
                        │ CREATED_AT            │
                        │ CREATED_BY            │
                        └──────────┬───────────┘
                                   │
              ┌────────────────────┼────────────────────┐
              │                    │                     │
     ┌────────▼────────┐  ┌───────▼────────┐  ┌────────▼────────┐
     │ PERSON_CONTACT   │  │ PERSON_ADDRESS  │  │ PERSON_EMPLOYMENT│
     │─────────────────│  │────────────────│  │─────────────────│
     │ PERSON_ID (FK)   │  │ PERSON_ID (FK)  │  │ PERSON_ID (FK)   │
     │ MOBILE_NUMBER    │  │ ADDRESS_LINE_1  │  │ EMPLOYMENT_STATUS │
     │ ALTERNATE_MOBILE │  │ ADDRESS_LINE_2  │  │ EMPLOYMENT_TYPE   │
     │ EMAIL_ADDRESS    │  │ CITY            │  │ INCOME_FREQUENCY  │
     │ ALTERNATE_EMAIL  │  │ STATE_PROVINCE  │  │ COMPANY           │
     └─────────────────┘  │ COUNTRY         │  │ JOB_TITLE         │
                           │ POSTAL_ZIP_CODE │  │ YEARS_OF_EMP      │
                           │ ADDRESS_TYPE    │  │ WORK_LOCATION     │
                           └────────────────┘  └──────────────────┘

     ┌─────────────────┐  ┌────────────────┐  ┌──────────────────┐
     │ PERSON_FINANCIAL │  │ PERSON_HEALTH   │  │ PERSON_INSURANCE  │
     │─────────────────│  │────────────────│  │──────────────────│
     │ PERSON_ID (FK)   │  │ PERSON_ID (FK)  │  │ PERSON_ID (FK)    │
     │ INCOME_BAND      │  │ HAS_DIABETES    │  │ COVERAGE_STATUS   │
     │ ASSET_BAND       │  │ HAS_HYPERTENSION│  │ COVERAGE_TYPE     │
     │ ITR_FILING_FLAG  │  │ HAS_HEART_DISEASE│ │ ACTIVE_POLICY_CNT │
     │ PENSION_INCOME   │  │ CONDITION_COUNT │  │ ANNUAL_PREMIUM    │
     │ TDS_INDICATOR    │  │ LIVING_SITUATION│  │ IS_UNINSURED      │
     │ AADHAAR_VERIFIED │  │ LIVING_ALONE    │  └──────────────────┘
     │ PAN_VERIFIED     │  │ CARE_NEEDS      │
     └─────────────────┘  └────────────────┘

     ┌─────────────────┐  ┌────────────────────────┐  ┌───────────────┐
     │ PERSON_CONSENT   │  │ PERSON_SERVICE_PREF     │  │ PERSON_EMERG  │
     │─────────────────│  │────────────────────────│  │ _CONTACT      │
     │ PERSON_ID (FK)   │  │ PERSON_ID (FK)          │  │───────────────│
     │ MARKETING_FLAG   │  │ WANTS_TELEMEDICINE      │  │ PERSON_ID (FK)│
     │ HEALTH_DATA_FLAG │  │ WANTS_HOME_VISIT        │  │ CONTACT_NAME  │
     └─────────────────┘  │ WANTS_ELDER_CARE        │  │ RELATIONSHIP  │
                           │ WANTS_FINANCIAL_ADVICE  │  │ MOBILE_NUMBER │
     ┌─────────────────┐  │ WANTS_CHECKUP           │  │ EMAIL_ADDRESS │
     │ PERSON_PREFERENCE│  └────────────────────────┘  └───────────────┘
     │─────────────────│
     │ PERSON_ID (FK)   │
     │ PREF_LANGUAGE    │
     │ PREF_CONTACT_MTD │
     │ NOTES            │
     └─────────────────┘
```

### Table Summary

| # | Table                        | Purpose                                 | Insert condition                    |
|---|------------------------------|-----------------------------------------|-------------------------------------|
| 1 | `PERSON`                     | Core identity and demographics          | Always (required fields)            |
| 2 | `PERSON_CONTACT`             | Phone and email                         | Always                              |
| 3 | `PERSON_ADDRESS`             | Residential / permanent address         | If any address field is filled      |
| 4 | `PERSON_EMPLOYMENT`          | Job and income details                  | If employment status is selected    |
| 5 | `PERSON_FINANCIAL`           | Income band, tax, verification flags    | Always                              |
| 6 | `PERSON_HEALTH`              | Conditions, living situation, care needs| Always                              |
| 7 | `PERSON_INSURANCE`           | Coverage status, policies, premiums     | Always                              |
| 8 | `PERSON_CONSENT`             | Marketing and health-data consent       | Always                              |
| 9 | `PERSON_SERVICE_PREFERENCE`  | Desired services (telemedicine, etc.)   | Always                              |
| 10| `PERSON_EMERGENCY_CONTACT`   | Emergency contact details               | If emergency contact name is filled |
| 11| `PERSON_PREFERENCE`          | Language, contact method, notes         | Always                              |

---

## Data Flow

### Registration (Write Path)

```
User fills form
       │
       ▼
┌──────────────┐     Fail
│  Client-side  │────────────► Display error messages
│  Validation   │              (name, state, phone, email required)
│  (regex)      │
└──────┬───────┘
       │ Pass
       ▼
┌──────────────┐
│  Generate     │  PERSON_ID_SEQ.NEXTVAL → "RE-00042"
│  Person ID    │  (or use custom ID if provided)
└──────┬───────┘
       │
       ▼
┌──────────────────────────────────────────────────┐
│  Sequential INSERTs via Snowpark session.sql()   │
│                                                   │
│  1. INSERT INTO PERSON                            │
│  2. INSERT INTO PERSON_CONTACT                    │
│  3. INSERT INTO PERSON_ADDRESS       (conditional)│
│  4. INSERT INTO PERSON_EMPLOYMENT    (conditional)│
│  5. INSERT INTO PERSON_FINANCIAL                  │
│  6. INSERT INTO PERSON_HEALTH                     │
│  7. INSERT INTO PERSON_INSURANCE                  │
│  8. INSERT INTO PERSON_CONSENT                    │
│  9. INSERT INTO PERSON_SERVICE_PREFERENCE         │
│ 10. INSERT INTO PERSON_EMERGENCY_CONTACT (cond.)  │
│ 11. INSERT INTO PERSON_PREFERENCE                 │
└──────────────────────┬───────────────────────────┘
                       │
                       ▼
              Set session state flags
              (form_submitted=True, last_person_id)
                       │
                       ▼
                   st.rerun()
                       │
                       ▼
              Display success banner
```

### Profile Viewing (Read Path — currently hidden from navigation)

```
Load all profiles
   │
   │  SELECT PERSON + LEFT JOIN PERSON_CONTACT
   │  ORDER BY CREATED_AT DESC
   │  (TTL cache: 30 seconds)
   ▼
┌──────────────────────┐
│  Searchable DataTable │ ← filter by name / ID / email
│  (single-row select)  │
└──────────┬───────────┘
           │ User selects a row
           ▼
┌──────────────────────┐
│  10 parallel queries  │ ← one per detail table
│  (TTL cache: 15 sec)  │    keyed on PERSON_ID
└──────────┬───────────┘
           │
           ▼
  Render 5 rows × 2 columns of detail cards
  (Personal, Contact, Address, Employment,
   Financial, Health, Insurance, Consent,
   Emergency, Preferences)
```

---

## Validation Rules

| Field             | Rule                                               |
|-------------------|----------------------------------------------------|
| Full name         | Required, non-empty after trim                     |
| State             | Required, must select from dropdown                |
| Mobile number     | Required, 7-15 digits after stripping formatting   |
| Email             | Required, regex `^[a-zA-Z0-9._%+-]+@...`          |
| Alternate email   | Optional, same regex if provided                   |
| Alternate mobile  | Optional, same digit rule if provided              |
| Emergency email   | Optional, same regex if provided                   |
| Emergency mobile  | Optional, same digit rule if provided              |

---

## Key Design Decisions

1. **Normalized schema** — Each domain (contact, health, financial, etc.) is a separate table rather than a wide single table. This keeps optional sections sparse and supports independent evolution of each domain.

2. **Sequence-based IDs** — `PERSON_ID_SEQ` generates monotonically increasing IDs formatted as `RE-XXXXX`. Users can override with a custom ID.

3. **Parameterized SQL** — All INSERTs use `:param` bind variables, preventing SQL injection.

4. **Conditional inserts** — Address and employment rows are only created when the user fills in at least one field. Emergency contact requires a name. All other tables are always inserted (with NULL for unfilled optional columns).

5. **No transactions** — INSERTs are issued sequentially without an explicit `BEGIN`/`COMMIT`. A failure mid-save could leave partial data.

6. **Single-file app** — The entire application lives in `streamlit_app.py` (~644 lines) with no external modules, pages, or components.

7. **TTL caching** — Profile list queries are cached for 30 seconds; detail queries for 15 seconds. The connection itself uses `SNOWFLAKE_CONNECTION_TTL` from the environment.
