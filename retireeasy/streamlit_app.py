import os
import re
from datetime import date, timedelta

import streamlit as st

st.set_page_config(page_title="Retire Easy", page_icon="🛡️", layout="wide")

conn = st.connection("snowflake", ttl=os.getenv("SNOWFLAKE_CONNECTION_TTL"))

# ── Session state defaults ──
st.session_state.setdefault("form_submitted", False)
st.session_state.setdefault("last_person_id", None)

SCHEMA = "PROTECT360_DB.SURVEY"

# ── Reference data ──
INDIAN_STATES = [
    "", "AN", "AP", "AR", "AS", "BR", "CG", "CH", "DD", "DL", "GA",
    "GJ", "HP", "HR", "JH", "JK", "KA", "KL", "LA", "LD", "MH",
    "ML", "MN", "MP", "MZ", "NL", "OD", "PB", "PY", "RJ", "SK",
    "TN", "TR", "TS", "UK", "UP", "WB",
]
STATE_LABELS = {
    "AN": "Andaman & Nicobar", "AP": "Andhra Pradesh", "AR": "Arunachal Pradesh",
    "AS": "Assam", "BR": "Bihar", "CG": "Chhattisgarh", "CH": "Chandigarh",
    "DD": "Daman & Diu", "DL": "Delhi", "GA": "Goa", "GJ": "Gujarat",
    "HP": "Himachal Pradesh", "HR": "Haryana", "JH": "Jharkhand",
    "JK": "Jammu & Kashmir", "KA": "Karnataka", "KL": "Kerala", "LA": "Ladakh",
    "LD": "Lakshadweep", "MH": "Maharashtra", "ML": "Meghalaya", "MN": "Manipur",
    "MP": "Madhya Pradesh", "MZ": "Mizoram", "NL": "Nagaland", "OD": "Odisha",
    "PB": "Punjab", "PY": "Puducherry", "RJ": "Rajasthan", "SK": "Sikkim",
    "TN": "Tamil Nadu", "TR": "Tripura", "TS": "Telangana", "UK": "Uttarakhand",
    "UP": "Uttar Pradesh", "WB": "West Bengal",
}
GENDER_OPTIONS = ["", "Male", "Female", "Non-binary", "Prefer not to say"]
MARITAL_OPTIONS = ["", "Single", "Married", "Divorced", "Widowed", "Other"]
EMPLOYMENT_STATUS_OPTIONS = ["", "Employed", "Self-employed", "Student", "Retired", "Unemployed", "Other"]
EMPLOYMENT_TYPE_OPTIONS = ["", "GIG_WORKER", "DAILY_WAGE", "SELF_EMPLOYED", "RETIRED", "SALARIED"]
INCOME_FREQUENCY_OPTIONS = ["", "DAILY", "MONTHLY", "IRREGULAR"]
INCOME_BAND_OPTIONS = ["", "BELOW_1L", "1L_3L", "3L_5L", "5L_10L", "ABOVE_10L"]
ASSET_BAND_OPTIONS = ["", "BELOW_5L", "5L_20L", "20L_50L", "50L_1CR", "ABOVE_1CR"]
COVERAGE_STATUS_OPTIONS = ["", "ACTIVE", "LAPSED", "EXPIRED", "NONE"]
COVERAGE_TYPE_OPTIONS = ["", "HEALTH", "LIFE", "TERM", "ACCIDENT", "PENSION", "MULTIPLE"]
LIVING_SITUATION_OPTIONS = ["", "WITH_FAMILY", "WITH_SPOUSE", "ALONE", "WITH_CAREGIVER", "INSTITUTION"]
RELATIONSHIP_OPTIONS = ["", "Spouse", "Parent", "Sibling", "Child", "Friend", "Colleague", "Other"]
LANGUAGE_OPTIONS = [
    "", "English", "Hindi", "Tamil", "Telugu", "Kannada", "Malayalam",
    "Bengali", "Marathi", "Gujarati", "Punjabi", "Urdu",
]
CONTACT_METHOD_OPTIONS = ["Phone", "Email", "SMS"]


def validate_email(email: str) -> bool:
    if not email:
        return False
    return bool(re.match(r"^[a-zA-Z0-9._%+\-]+@[a-zA-Z0-9.\-]+\.[a-zA-Z]{2,}$", email))


def validate_phone(phone: str) -> bool:
    if not phone:
        return False
    digits = re.sub(r"[\s\-\(\)\+]", "", phone)
    return digits.isdigit() and 7 <= len(digits) <= 15


def calculate_age(dob: date) -> int:
    today = date.today()
    return today.year - dob.year - ((today.month, today.day) < (dob.month, dob.day))


def generate_person_id() -> str:
    session = conn.session()
    result = session.sql("SELECT PROTECT360_DB.SURVEY.PERSON_ID_SEQ.NEXTVAL AS ID").collect()
    seq = int(result[0]["ID"])
    return f"RE-{seq:05d}"


# ── Sidebar ──
st.sidebar.markdown(
    "<h2 style='color:#FFCC00;'>Retire Easy</h2>"
    "<p style='color:#666;font-size:0.85em;'>Retirement Planning Survey</p>",
    unsafe_allow_html=True,
)
page = st.sidebar.radio(
    "Navigate",
    ["➕ New person", "📋 View profiles"],
    label_visibility="collapsed",
)


# ═══════════════════════════════════════════════════════
# PAGE 1: NEW PERSON FORM
# ═══════════════════════════════════════════════════════
if page == "➕ New person":
    st.markdown("<h1 style='color:#000;'>New Person Registration</h1>", unsafe_allow_html=True)
    st.caption("Complete the sections below to register a new person profile. Fields marked with * are required.")

    if st.session_state.form_submitted and st.session_state.last_person_id:
        st.success(f"Person saved successfully. Person ID: **{st.session_state.last_person_id}**")
        st.session_state.form_submitted = False

    errors: list[str] = []

    # ── Section 1: Personal information ──
    with st.expander("👤 Personal information", expanded=True):
        p_col1, p_col2 = st.columns(2)
        with p_col1:
            full_name = st.text_input("Full name *", key="full_name", placeholder="e.g. Raghunath Mandal")
            dob = st.date_input("Date of birth", key="dob", value=None, min_value=date(1900, 1, 1), max_value=date.today())
            gender = st.selectbox("Gender", GENDER_OPTIONS, key="gender")
        with p_col2:
            state_code = st.selectbox(
                "State *",
                INDIAN_STATES,
                key="state_code",
                format_func=lambda x: f"{x} — {STATE_LABELS[x]}" if x else "",
            )
            postcode = st.text_input("PIN code", key="postcode", placeholder="e.g. 110001")
            marital_status = st.selectbox("Marital status", MARITAL_OPTIONS, key="marital_status")
            if dob:
                age = calculate_age(dob)
                st.metric("Age (calculated)", age)
            else:
                age = None

    # ── Section 2: Contact information ──
    with st.expander("📞 Contact information", expanded=True):
        c_col1, c_col2 = st.columns(2)
        with c_col1:
            mobile = st.text_input("Mobile number *", key="mobile", placeholder="e.g. +91 98765 43210")
            email = st.text_input("Email address *", key="email", placeholder="e.g. raghunath@example.com")
        with c_col2:
            alt_mobile = st.text_input("Alternate mobile number", key="alt_mobile")
            alt_email = st.text_input("Alternate email address", key="alt_email")

    # ── Section 3: Address information ──
    with st.expander("🏠 Address information", expanded=False):
        a_col1, a_col2 = st.columns(2)
        with a_col1:
            addr_line1 = st.text_input("Address line 1", key="addr1")
            addr_line2 = st.text_input("Address line 2", key="addr2")
            city = st.text_input("City", key="city")
        with a_col2:
            state_province = st.text_input("District / Region", key="state_prov")
            postal_code = st.text_input("PIN code (address)", key="postal")
            address_type = st.selectbox("Address type", ["Residential", "Permanent", "Other"], key="addr_type")

    # ── Section 4: Employment information ──
    with st.expander("💼 Employment information", expanded=False):
        e_col1, e_col2 = st.columns(2)
        with e_col1:
            emp_status = st.selectbox("Employment status", EMPLOYMENT_STATUS_OPTIONS, key="emp_status")
            emp_type = st.selectbox("Employment type", EMPLOYMENT_TYPE_OPTIONS, key="emp_type")
            income_freq = st.selectbox("Income frequency", INCOME_FREQUENCY_OPTIONS, key="income_freq")
        with e_col2:
            company = st.text_input("Company / Organisation", key="company")
            job_title = st.text_input("Job title", key="job_title")
            years_emp = st.number_input("Years of employment", min_value=0.0, max_value=60.0, value=0.0, step=0.5, key="years_emp")
            work_location = st.text_input("Work location", key="work_loc")

    # ── Section 5: Financial profile ──
    with st.expander("💰 Financial profile", expanded=False):
        f_col1, f_col2 = st.columns(2)
        with f_col1:
            income_band = st.selectbox("Income band (annual)", INCOME_BAND_OPTIONS, key="income_band",
                                       format_func=lambda x: x.replace("_", "-") if x else "")
            asset_band = st.selectbox("Asset band", ASSET_BAND_OPTIONS, key="asset_band",
                                      format_func=lambda x: x.replace("_", "-") if x else "")
            itr_filing = st.checkbox("Files Income Tax Return (ITR)", key="itr_filing")
        with f_col2:
            pension_income = st.checkbox("Has pension income", key="pension_income")
            tds_indicator = st.checkbox("TDS deductions present", key="tds_indicator")
            aadhaar_verified = st.checkbox("Aadhaar verified", key="aadhaar_verified")
            pan_verified = st.checkbox("PAN verified", key="pan_verified")

    # ── Section 6: Health profile ──
    with st.expander("🏥 Health profile", expanded=False):
        h_col1, h_col2 = st.columns(2)
        with h_col1:
            st.markdown("**Pre-existing conditions**")
            has_diabetes = st.checkbox("Diabetes", key="has_diabetes")
            has_hypertension = st.checkbox("Hypertension", key="has_hypertension")
            has_heart_disease = st.checkbox("Heart disease", key="has_heart_disease")
        with h_col2:
            living_situation = st.selectbox("Living situation", LIVING_SITUATION_OPTIONS, key="living_situation",
                                            format_func=lambda x: x.replace("_", " ").title() if x else "")
            living_alone = st.checkbox("Living alone", key="living_alone")
            care_needs = st.checkbox("Has care needs (requires assistance)", key="care_needs")

    # ── Section 7: Insurance & coverage ──
    with st.expander("📋 Insurance & coverage", expanded=False):
        i_col1, i_col2 = st.columns(2)
        with i_col1:
            coverage_status = st.selectbox("Current coverage status", COVERAGE_STATUS_OPTIONS, key="coverage_status")
            coverage_type = st.selectbox("Coverage type", COVERAGE_TYPE_OPTIONS, key="coverage_type")
            is_uninsured = st.checkbox("Currently uninsured (no active policy)", key="is_uninsured")
        with i_col2:
            active_policy_count = st.number_input("Active policy count", min_value=0, max_value=20, value=0, key="active_policies")
            annual_premium = st.number_input("Total annual premium (INR)", min_value=0.0, max_value=10000000.0, value=0.0, step=1000.0, key="annual_premium")

    # ── Section 8: Consent ──
    with st.expander("✅ Consent", expanded=False):
        cn_col1, cn_col2 = st.columns(2)
        with cn_col1:
            marketing_consent = st.checkbox("I consent to receive marketing communications", key="marketing_consent")
        with cn_col2:
            health_data_consent = st.checkbox("I consent to share health data for analysis", key="health_data_consent")

    # ── Section 9: Service preferences ──
    with st.expander("🎯 Service preferences", expanded=False):
        st.markdown("**Which services are you interested in?**")
        sv_col1, sv_col2 = st.columns(2)
        with sv_col1:
            wants_telemedicine = st.checkbox("Telemedicine consultation", key="wants_telemedicine")
            wants_home_visit = st.checkbox("Home healthcare visit", key="wants_home_visit")
            wants_elder_care = st.checkbox("Elder care navigation", key="wants_elder_care")
        with sv_col2:
            wants_financial_advice = st.checkbox("Financial planning advice", key="wants_financial_advice")
            wants_checkup = st.checkbox("Preventive health checkup", key="wants_checkup")

    # ── Section 10: Emergency contact ──
    with st.expander("🚨 Emergency contact", expanded=False):
        em_col1, em_col2 = st.columns(2)
        with em_col1:
            ec_name = st.text_input("Emergency contact name", key="ec_name")
            ec_relationship = st.selectbox("Relationship", RELATIONSHIP_OPTIONS, key="ec_rel")
        with em_col2:
            ec_mobile = st.text_input("Emergency contact mobile", key="ec_mobile")
            ec_email = st.text_input("Emergency contact email", key="ec_email")

    # ── Section 11: Preferences & notes ──
    with st.expander("⚙️ Preferences & additional information", expanded=False):
        pr_col1, pr_col2 = st.columns(2)
        with pr_col1:
            pref_lang = st.selectbox("Preferred language", LANGUAGE_OPTIONS, key="pref_lang")
            pref_contact = st.radio("Preferred contact method", CONTACT_METHOD_OPTIONS, key="pref_contact", horizontal=True)
        with pr_col2:
            custom_id = st.text_input("Person ID (leave blank to auto-generate)", key="custom_id")
        notes = st.text_area("Notes / Additional information", key="notes", height=100)

    # ── Save ──
    if st.button("Save person", type="primary", use_container_width=True):
        if not full_name or not full_name.strip():
            errors.append("Full name is required.")
        if not state_code:
            errors.append("State is required.")
        if not mobile or not validate_phone(mobile):
            errors.append("A valid mobile number is required (7-15 digits).")
        if not email or not validate_email(email):
            errors.append("A valid email address is required.")
        if alt_email and not validate_email(alt_email):
            errors.append("Alternate email address is not in a valid format.")
        if alt_mobile and not validate_phone(alt_mobile):
            errors.append("Alternate mobile number is not valid.")
        if ec_email and not validate_email(ec_email):
            errors.append("Emergency contact email is not in a valid format.")
        if ec_mobile and not validate_phone(ec_mobile):
            errors.append("Emergency contact mobile is not valid.")

        if errors:
            for err in errors:
                st.error(err)
        else:
            with st.spinner("Saving person profile..."):
                person_id = custom_id.strip() if custom_id and custom_id.strip() else generate_person_id()
                session = conn.session()

                session.sql(
                    f"""INSERT INTO {SCHEMA}.PERSON
                        (PERSON_ID, FULL_NAME, DATE_OF_BIRTH, GENDER, NATIONALITY, MARITAL_STATUS, STATE_CODE, POSTCODE, CREATED_BY)
                        VALUES (:pid, :name, :dob, :gender, 'India', :marital, :state, :postcode, CURRENT_USER())""",
                    params={
                        "pid": person_id, "name": full_name.strip(),
                        "dob": str(dob) if dob else None, "gender": gender or None,
                        "marital": marital_status or None, "state": state_code or None,
                        "postcode": postcode.strip() or None,
                    },
                ).collect()

                session.sql(
                    f"""INSERT INTO {SCHEMA}.PERSON_CONTACT
                        (PERSON_ID, MOBILE_NUMBER, ALTERNATE_MOBILE, EMAIL_ADDRESS, ALTERNATE_EMAIL)
                        VALUES (:pid, :mob, :alt_mob, :email, :alt_email)""",
                    params={
                        "pid": person_id, "mob": mobile.strip(),
                        "alt_mob": alt_mobile.strip() or None,
                        "email": email.strip(), "alt_email": alt_email.strip() or None,
                    },
                ).collect()

                if any([addr_line1, city, state_province, postal_code]):
                    session.sql(
                        f"""INSERT INTO {SCHEMA}.PERSON_ADDRESS
                            (PERSON_ID, ADDRESS_LINE_1, ADDRESS_LINE_2, CITY, STATE_PROVINCE,
                             COUNTRY, POSTAL_ZIP_CODE, ADDRESS_TYPE)
                            VALUES (:pid, :a1, :a2, :city, :state, 'India', :zip, :atype)""",
                        params={
                            "pid": person_id, "a1": addr_line1.strip() or None,
                            "a2": addr_line2.strip() or None, "city": city.strip() or None,
                            "state": state_province.strip() or None,
                            "zip": postal_code.strip() or None, "atype": address_type,
                        },
                    ).collect()

                if emp_status:
                    session.sql(
                        f"""INSERT INTO {SCHEMA}.PERSON_EMPLOYMENT
                            (PERSON_ID, EMPLOYMENT_STATUS, EMPLOYMENT_TYPE_CODE, INCOME_FREQUENCY,
                             COMPANY_ORGANISATION, JOB_TITLE, YEARS_OF_EMPLOYMENT, WORK_LOCATION)
                            VALUES (:pid, :status, :etype, :ifreq, :company, :title, :years, :loc)""",
                        params={
                            "pid": person_id, "status": emp_status,
                            "etype": emp_type or None, "ifreq": income_freq or None,
                            "company": company.strip() or None, "title": job_title.strip() or None,
                            "years": years_emp if years_emp > 0 else None,
                            "loc": work_location.strip() or None,
                        },
                    ).collect()

                session.sql(
                    f"""INSERT INTO {SCHEMA}.PERSON_FINANCIAL
                        (PERSON_ID, INCOME_BAND, ASSET_BAND, ITR_FILING_FLAG, PENSION_INCOME_FLAG,
                         TDS_INDICATOR, AADHAAR_VERIFIED_FLAG, PAN_VERIFIED_FLAG)
                        VALUES (:pid, :ib, :ab, :itr, :pension, :tds, :aadhaar, :pan)""",
                    params={
                        "pid": person_id, "ib": income_band or None, "ab": asset_band or None,
                        "itr": itr_filing, "pension": pension_income, "tds": tds_indicator,
                        "aadhaar": aadhaar_verified, "pan": pan_verified,
                    },
                ).collect()

                condition_count = sum([has_diabetes, has_hypertension, has_heart_disease])
                session.sql(
                    f"""INSERT INTO {SCHEMA}.PERSON_HEALTH
                        (PERSON_ID, HAS_DIABETES, HAS_HYPERTENSION, HAS_HEART_DISEASE,
                         CONDITION_COUNT, LIVING_SITUATION, LIVING_ALONE_FLAG, CARE_NEEDS_FLAG)
                        VALUES (:pid, :dia, :hyp, :heart, :cnt, :living, :alone, :care)""",
                    params={
                        "pid": person_id, "dia": has_diabetes, "hyp": has_hypertension,
                        "heart": has_heart_disease, "cnt": condition_count,
                        "living": living_situation or None, "alone": living_alone, "care": care_needs,
                    },
                ).collect()

                session.sql(
                    f"""INSERT INTO {SCHEMA}.PERSON_INSURANCE
                        (PERSON_ID, CURRENT_COVERAGE_STATUS, CURRENT_COVERAGE_TYPE,
                         ACTIVE_POLICY_COUNT, TOTAL_ANNUAL_PREMIUM, IS_UNINSURED)
                        VALUES (:pid, :status, :ctype, :policies, :premium, :uninsured)""",
                    params={
                        "pid": person_id, "status": coverage_status or None,
                        "ctype": coverage_type or None,
                        "policies": active_policy_count, "premium": annual_premium,
                        "uninsured": is_uninsured,
                    },
                ).collect()

                session.sql(
                    f"""INSERT INTO {SCHEMA}.PERSON_CONSENT
                        (PERSON_ID, MARKETING_CONSENT_FLAG, HEALTH_DATA_CONSENT_FLAG)
                        VALUES (:pid, :mkt, :health)""",
                    params={"pid": person_id, "mkt": marketing_consent, "health": health_data_consent},
                ).collect()

                session.sql(
                    f"""INSERT INTO {SCHEMA}.PERSON_SERVICE_PREFERENCE
                        (PERSON_ID, WANTS_TELEMEDICINE, WANTS_HOME_VISIT, WANTS_ELDER_CARE,
                         WANTS_FINANCIAL_ADVICE, WANTS_CHECKUP)
                        VALUES (:pid, :tele, :home, :elder, :fin, :checkup)""",
                    params={
                        "pid": person_id, "tele": wants_telemedicine, "home": wants_home_visit,
                        "elder": wants_elder_care, "fin": wants_financial_advice,
                        "checkup": wants_checkup,
                    },
                ).collect()

                if ec_name and ec_name.strip():
                    session.sql(
                        f"""INSERT INTO {SCHEMA}.PERSON_EMERGENCY_CONTACT
                            (PERSON_ID, CONTACT_NAME, RELATIONSHIP, MOBILE_NUMBER, EMAIL_ADDRESS)
                            VALUES (:pid, :name, :rel, :mob, :email)""",
                        params={
                            "pid": person_id, "name": ec_name.strip(),
                            "rel": ec_relationship or None,
                            "mob": ec_mobile.strip() or None, "email": ec_email.strip() or None,
                        },
                    ).collect()

                session.sql(
                    f"""INSERT INTO {SCHEMA}.PERSON_PREFERENCE
                        (PERSON_ID, PREFERRED_LANGUAGE, PREFERRED_CONTACT_METHOD, NOTES)
                        VALUES (:pid, :lang, :method, :notes)""",
                    params={
                        "pid": person_id, "lang": pref_lang or None,
                        "method": pref_contact, "notes": notes.strip() or None,
                    },
                ).collect()

            st.session_state.form_submitted = True
            st.session_state.last_person_id = person_id
            st.rerun()


# ═══════════════════════════════════════════════════════
# PAGE 2: VIEW PROFILES
# ═══════════════════════════════════════════════════════
elif page == "📋 View profiles":
    st.markdown("<h1 style='color:#000;'>Person Profiles</h1>", unsafe_allow_html=True)
    st.caption("Search and view registered person profiles.")

    with st.spinner("Loading profiles..."):
        profiles = conn.query(
            f"""SELECT p.PERSON_ID, p.FULL_NAME, p.DATE_OF_BIRTH, p.GENDER, p.STATE_CODE,
                       p.MARITAL_STATUS, p.CREATED_AT, p.CREATED_BY,
                       c.MOBILE_NUMBER, c.EMAIL_ADDRESS
                FROM {SCHEMA}.PERSON p
                LEFT JOIN {SCHEMA}.PERSON_CONTACT c ON p.PERSON_ID = c.PERSON_ID
                ORDER BY p.CREATED_AT DESC""",
            ttl=timedelta(seconds=30),
        )

    if profiles.empty:
        st.info("No person profiles found. Create one from the **New person** page.")
        st.stop()

    search = st.text_input("Search by name, ID, or email", placeholder="e.g. Raghunath or RE-00001", key="search_profiles")

    filtered = profiles.copy()
    if search:
        q = search.lower()
        filtered = filtered[
            filtered["FULL_NAME"].str.lower().str.contains(q, na=False)
            | filtered["PERSON_ID"].str.lower().str.contains(q, na=False)
            | filtered["EMAIL_ADDRESS"].str.lower().str.contains(q, na=False)
        ]

    st.caption(f"Showing {len(filtered)} of {len(profiles)} profiles")

    st.dataframe(
        filtered[["PERSON_ID", "FULL_NAME", "GENDER", "STATE_CODE", "MOBILE_NUMBER", "EMAIL_ADDRESS", "CREATED_AT"]],
        use_container_width=True, hide_index=True,
        on_select="rerun", selection_mode="single-row", key="profile_table",
    )

    selection = st.session_state.get("profile_table")
    if selection and selection.get("selection") and selection["selection"].get("rows"):
        idx = selection["selection"]["rows"][0]
        chosen = filtered.iloc[idx]
        pid = chosen["PERSON_ID"]

        st.subheader(f"{chosen['FULL_NAME']} — {pid}", anchor=False)

        with st.spinner("Loading full profile..."):
            address = conn.query(f"SELECT * FROM {SCHEMA}.PERSON_ADDRESS WHERE PERSON_ID = ?", params=[pid], ttl=timedelta(seconds=15))
            employment = conn.query(f"SELECT * FROM {SCHEMA}.PERSON_EMPLOYMENT WHERE PERSON_ID = ?", params=[pid], ttl=timedelta(seconds=15))
            emergency = conn.query(f"SELECT * FROM {SCHEMA}.PERSON_EMERGENCY_CONTACT WHERE PERSON_ID = ?", params=[pid], ttl=timedelta(seconds=15))
            preference = conn.query(f"SELECT * FROM {SCHEMA}.PERSON_PREFERENCE WHERE PERSON_ID = ?", params=[pid], ttl=timedelta(seconds=15))
            contact_detail = conn.query(f"SELECT ALTERNATE_MOBILE, ALTERNATE_EMAIL FROM {SCHEMA}.PERSON_CONTACT WHERE PERSON_ID = ?", params=[pid], ttl=timedelta(seconds=15))
            financial = conn.query(f"SELECT * FROM {SCHEMA}.PERSON_FINANCIAL WHERE PERSON_ID = ?", params=[pid], ttl=timedelta(seconds=15))
            health = conn.query(f"SELECT * FROM {SCHEMA}.PERSON_HEALTH WHERE PERSON_ID = ?", params=[pid], ttl=timedelta(seconds=15))
            insurance = conn.query(f"SELECT * FROM {SCHEMA}.PERSON_INSURANCE WHERE PERSON_ID = ?", params=[pid], ttl=timedelta(seconds=15))
            consent = conn.query(f"SELECT * FROM {SCHEMA}.PERSON_CONSENT WHERE PERSON_ID = ?", params=[pid], ttl=timedelta(seconds=15))
            services = conn.query(f"SELECT * FROM {SCHEMA}.PERSON_SERVICE_PREFERENCE WHERE PERSON_ID = ?", params=[pid], ttl=timedelta(seconds=15))

        col1, col2 = st.columns(2)
        with col1:
            with st.container(border=True):
                st.markdown("**👤 Personal information**")
                st.markdown(f"- **Full name:** {chosen['FULL_NAME']}")
                if chosen["DATE_OF_BIRTH"]:
                    dob_val = chosen["DATE_OF_BIRTH"]
                    age_val = calculate_age(dob_val) if isinstance(dob_val, date) else "—"
                    st.markdown(f"- **Date of birth:** {dob_val}  (Age: {age_val})")
                st.markdown(f"- **Gender:** {chosen.get('GENDER') or '—'}")
                st.markdown(f"- **State:** {chosen.get('STATE_CODE') or '—'}")
                st.markdown(f"- **Marital status:** {chosen.get('MARITAL_STATUS') or '—'}")

        with col2:
            with st.container(border=True):
                st.markdown("**📞 Contact information**")
                st.markdown(f"- **Mobile:** {chosen.get('MOBILE_NUMBER') or '—'}")
                st.markdown(f"- **Email:** {chosen.get('EMAIL_ADDRESS') or '—'}")
                if not contact_detail.empty:
                    cr = contact_detail.iloc[0]
                    if cr.get("ALTERNATE_MOBILE"):
                        st.markdown(f"- **Alt mobile:** {cr['ALTERNATE_MOBILE']}")
                    if cr.get("ALTERNATE_EMAIL"):
                        st.markdown(f"- **Alt email:** {cr['ALTERNATE_EMAIL']}")

        col3, col4 = st.columns(2)
        with col3:
            with st.container(border=True):
                st.markdown("**🏠 Address information**")
                if address.empty:
                    st.caption("No address on file.")
                else:
                    a = address.iloc[0]
                    parts = [v for v in [a.get("ADDRESS_LINE_1"), a.get("ADDRESS_LINE_2")] if v]
                    if parts:
                        st.markdown(f"- **Street:** {', '.join(parts)}")
                    loc_parts = [v for v in [a.get("CITY"), a.get("STATE_PROVINCE")] if v]
                    if loc_parts:
                        st.markdown(f"- **City / District:** {', '.join(loc_parts)}")
                    if a.get("POSTAL_ZIP_CODE"):
                        st.markdown(f"- **PIN code:** {a['POSTAL_ZIP_CODE']}")

        with col4:
            with st.container(border=True):
                st.markdown("**💼 Employment information**")
                if employment.empty:
                    st.caption("No employment details on file.")
                else:
                    e = employment.iloc[0]
                    if e.get("EMPLOYMENT_STATUS"):
                        st.markdown(f"- **Status:** {e['EMPLOYMENT_STATUS']}")
                    if e.get("EMPLOYMENT_TYPE_CODE"):
                        st.markdown(f"- **Type:** {e['EMPLOYMENT_TYPE_CODE']}")
                    if e.get("COMPANY_ORGANISATION"):
                        st.markdown(f"- **Company:** {e['COMPANY_ORGANISATION']}")

        col5, col6 = st.columns(2)
        with col5:
            with st.container(border=True):
                st.markdown("**💰 Financial profile**")
                if financial.empty:
                    st.caption("No financial data on file.")
                else:
                    fi = financial.iloc[0]
                    if fi.get("INCOME_BAND"):
                        st.markdown(f"- **Income band:** {fi['INCOME_BAND'].replace('_', '-')}")
                    st.markdown(f"- **ITR filed:** {'Yes' if fi.get('ITR_FILING_FLAG') else 'No'}")
                    st.markdown(f"- **Aadhaar verified:** {'Yes' if fi.get('AADHAAR_VERIFIED_FLAG') else 'No'}")
                    st.markdown(f"- **PAN verified:** {'Yes' if fi.get('PAN_VERIFIED_FLAG') else 'No'}")

        with col6:
            with st.container(border=True):
                st.markdown("**🏥 Health profile**")
                if health.empty:
                    st.caption("No health data on file.")
                else:
                    hl = health.iloc[0]
                    conditions_list = []
                    if hl.get("HAS_DIABETES"):
                        conditions_list.append("Diabetes")
                    if hl.get("HAS_HYPERTENSION"):
                        conditions_list.append("Hypertension")
                    if hl.get("HAS_HEART_DISEASE"):
                        conditions_list.append("Heart disease")
                    st.markdown(f"- **Conditions:** {', '.join(conditions_list) if conditions_list else 'None reported'}")
                    if hl.get("LIVING_SITUATION"):
                        st.markdown(f"- **Living situation:** {hl['LIVING_SITUATION'].replace('_', ' ').title()}")
                    st.markdown(f"- **Living alone:** {'Yes' if hl.get('LIVING_ALONE_FLAG') else 'No'}")
                    st.markdown(f"- **Care needs:** {'Yes' if hl.get('CARE_NEEDS_FLAG') else 'No'}")

        col7, col8 = st.columns(2)
        with col7:
            with st.container(border=True):
                st.markdown("**📋 Insurance & coverage**")
                if insurance.empty:
                    st.caption("No insurance data on file.")
                else:
                    ins = insurance.iloc[0]
                    if ins.get("CURRENT_COVERAGE_STATUS"):
                        st.markdown(f"- **Status:** {ins['CURRENT_COVERAGE_STATUS']}")
                    st.markdown(f"- **Active policies:** {int(ins.get('ACTIVE_POLICY_COUNT', 0))}")
                    st.markdown(f"- **Annual premium:** INR {ins.get('TOTAL_ANNUAL_PREMIUM', 0):,.0f}")
                    st.markdown(f"- **Uninsured:** {'Yes' if ins.get('IS_UNINSURED') else 'No'}")

        with col8:
            with st.container(border=True):
                st.markdown("**✅ Consent & services**")
                if not consent.empty:
                    cn = consent.iloc[0]
                    st.markdown(f"- **Marketing consent:** {'Yes' if cn.get('MARKETING_CONSENT_FLAG') else 'No'}")
                    st.markdown(f"- **Health data consent:** {'Yes' if cn.get('HEALTH_DATA_CONSENT_FLAG') else 'No'}")
                if not services.empty:
                    sv = services.iloc[0]
                    wanted = []
                    if sv.get("WANTS_TELEMEDICINE"):
                        wanted.append("Telemedicine")
                    if sv.get("WANTS_HOME_VISIT"):
                        wanted.append("Home visit")
                    if sv.get("WANTS_ELDER_CARE"):
                        wanted.append("Elder care")
                    if sv.get("WANTS_FINANCIAL_ADVICE"):
                        wanted.append("Financial advice")
                    if sv.get("WANTS_CHECKUP"):
                        wanted.append("Health checkup")
                    st.markdown(f"- **Services wanted:** {', '.join(wanted) if wanted else 'None selected'}")

        if not emergency.empty:
            with st.container(border=True):
                st.markdown("**🚨 Emergency contact**")
                ec = emergency.iloc[0]
                st.markdown(f"- **Name:** {ec.get('CONTACT_NAME', '—')}  |  **Relationship:** {ec.get('RELATIONSHIP', '—')}  |  **Mobile:** {ec.get('MOBILE_NUMBER', '—')}")

        st.caption(f"Created: {chosen.get('CREATED_AT', '—')} by {chosen.get('CREATED_BY', '—')}")
