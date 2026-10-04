# Protect360 AI — 5-page Customer 360 and Next Best Action dashboard
# Co-authored with CoCo
import os
import streamlit as st
from datetime import timedelta

st.set_page_config(page_title="Protect360 AI", page_icon="🛡️", layout="wide")

conn = st.connection("snowflake", ttl=os.getenv("SNOWFLAKE_CONNECTION_TTL"))

# ── Sidebar navigation ──
st.sidebar.markdown(
    "<h2 style='color:#FFCC00;'>Protect360 AI</h2>"
    "<p style='color:#666;font-size:0.85em;'>Customer 360 &amp; Next Best Action</p>",
    unsafe_allow_html=True,
)

# Handle pending navigation (must set before widget renders)
if "pending_nav" in st.session_state and st.session_state.pending_nav:
    st.session_state.nav_page = st.session_state.pending_nav
    st.session_state.pending_nav = None

page = st.sidebar.radio(
    "Navigate",
    ["Executive Overview", "Customer 360 Profile", "Risk & Propensity",
     "Next Best Action", "Governance Monitor"],
    label_visibility="collapsed",
    key="nav_page",
)

if "selected_customer_key" not in st.session_state:
    st.session_state.selected_customer_key = None
if "selected_customer_id" not in st.session_state:
    st.session_state.selected_customer_id = None
if "selected_customer_name" not in st.session_state:
    st.session_state.selected_customer_name = None


# ═══════════════════════════════════════════════════════
# PAGE 1: EXECUTIVE OVERVIEW
# ═══════════════════════════════════════════════════════
if page == "Executive Overview":
    st.markdown("<h1 style='color:#000;'>Executive Overview</h1>", unsafe_allow_html=True)

    with st.spinner("Loading KPIs..."):
        kpi = conn.query("SELECT * FROM PROTECT360_DB.GOLD.VW_EXECUTIVE_OVERVIEW", ttl=timedelta(minutes=5))

    if kpi.empty:
        st.warning("No executive overview data available.")
        st.stop()

    row = kpi.iloc[0]
    total = int(row['TOTAL_CUSTOMERS'])
    protection_gap_pct = round(int(row['PROTECTION_GAP_COUNT']) * 100.0 / total, 1) if total else 0
    dq_pass_pct = round(int(row['DQ_GREEN_COUNT']) * 100.0 / total, 1) if total else 0

    cols = st.columns(4)
    cols[0].metric("Total Customers", f"{total:,}", border=True)
    cols[1].metric("Protection Gap", f"{protection_gap_pct}%",
                   delta=f"{int(row['PROTECTION_GAP_COUNT'])} customers", delta_color="inverse", border=True)
    cols[2].metric("High Vulnerability", f"{int(row['HIGH_VULNERABILITY_COUNT'])}", border=True)
    cols[3].metric("DQ Pass Rate", f"{dq_pass_pct}%", border=True)

    c1, c2 = st.columns(2)
    with c1:
        with st.container(border=True):
            st.subheader("Top Actions (Rank 1)")
            with st.spinner("Loading actions..."):
                actions = conn.query("""
                    SELECT cat.ACTION_NAME, COUNT(*) AS CUSTOMERS
                    FROM PROTECT360_DB.GOLD.NEXT_BEST_ACTION nba
                    JOIN PROTECT360_DB.GOLD.NBA_ACTION_CATALOG cat ON nba.ACTION_KEY = cat.ACTION_KEY
                    WHERE nba.PRIORITY_RANK = 1
                    GROUP BY 1 ORDER BY 2 DESC
                """, ttl=timedelta(minutes=5))
            st.bar_chart(actions, x="ACTION_NAME", y="CUSTOMERS", horizontal=True)

    with c2:
        with st.container(border=True):
            st.subheader("High Priority by State")
            with st.spinner("Loading state data..."):
                states = conn.query("""
                    SELECT STATE_CODE, COUNT(*) AS CUSTOMERS
                    FROM PROTECT360_DB.GOLD.VW_HIGH_PRIORITY_CUSTOMERS
                    GROUP BY 1 ORDER BY 2 DESC
                """, ttl=timedelta(minutes=5))
            st.bar_chart(states, x="STATE_CODE", y="CUSTOMERS")

    ac1, ac2 = st.columns(2)
    with ac1:
        with st.container(border=True):
            st.subheader("Top 10 Vulnerable Customers (Tier 1)")
            with st.spinner("Loading urgent customers..."):
                urgent = conn.query("""
                    SELECT FULL_NAME, AGE, STATE_CODE, VULNERABILITY_SCORE, TOP_ACTION_NAME
                    FROM PROTECT360_DB.GOLD.VW_HIGH_PRIORITY_CUSTOMERS
                    WHERE URGENCY_TIER = 1
                    ORDER BY VULNERABILITY_SCORE DESC
                    LIMIT 10
                """, ttl=timedelta(minutes=5))
            st.dataframe(urgent, use_container_width=True, hide_index=True)

    with ac2:
        with st.container(border=True):
            st.subheader("Top 10 Critical Customers")
            st.caption("Near-retirement ITR filers (age 57–63) — uninsured prioritised")
            with st.spinner("Loading critical customers..."):
                critical = conn.query("""
                    SELECT FULL_NAME, AGE, STATE_CODE, INCOME_BAND, CAPACITY_SCORE,
                           CASE WHEN IS_UNINSURED THEN 'Yes' ELSE 'No' END AS UNINSURED,
                           TOP_ACTION_NAME
                    FROM PROTECT360_DB.GOLD.VW_ADVISOR_CUSTOMER_360
                    WHERE AGE BETWEEN 57 AND 63
                      AND ITR_FILING_FLAG = TRUE
                    ORDER BY IS_UNINSURED DESC, CAPACITY_SCORE DESC NULLS LAST,
                             TOP_ACTION_SCORE DESC NULLS LAST
                    LIMIT 10
                """, ttl=timedelta(minutes=5))
            st.dataframe(critical, use_container_width=True, hide_index=True)



# ═══════════════════════════════════════════════════════
# PAGE 2: CUSTOMER 360 PROFILE
# ═══════════════════════════════════════════════════════
elif page == "Customer 360 Profile":
    st.markdown("<h1 style='color:#000;'>Customer 360 Profile</h1>", unsafe_allow_html=True)

    with st.spinner("Loading customer data..."):
        all_customers = conn.query("""
            SELECT v.CUSTOMER_ID, v.FULL_NAME, v.AGE_BAND, v.STATE_CODE,
                   REPLACE(v.INCOME_BAND, '_', '-') AS INCOME_BAND,
                   CASE WHEN v.PROTECTION_GAP_FLAG THEN 'True' ELSE 'False' END AS PROTECTION_GAP_FLAG,
                   v.VULNERABILITY_CLASS, v.TOP_ACTION_NAME,
                   v.DATA_QUALITY_STATUS,
                   CASE
                       WHEN v.TOP_ACTION_NAME IS NOT NULL THEN 'Has Actions'
                       ELSE 'No Actions'
                   END AS NBA_STATUS,
                   CASE WHEN ao.CUSTOMER_KEY IS NOT NULL THEN 'Actioned'
                        ELSE 'Pending'
                   END AS DECISION_STATUS
            FROM PROTECT360_DB.GOLD.VW_ADVISOR_CUSTOMER_360 v
            LEFT JOIN (
                SELECT DISTINCT o.CUSTOMER_KEY
                FROM PROTECT360_DB.GOLD.ACTION_OUTCOME o
            ) ao ON MD5(v.CUSTOMER_ID) = ao.CUSTOMER_KEY
            ORDER BY v.CUSTOMER_ID
        """, ttl=timedelta(seconds=30))

    fc1, fc2, fc3, fc4 = st.columns([2, 1, 1, 1])
    with fc1:
        search = st.text_input("Search by customer name or ID", placeholder="e.g. Raghunath or CUST0001")
    with fc2:
        states_list = ["All"] + sorted(all_customers["STATE_CODE"].dropna().unique().tolist())
        sel_state = st.selectbox("State", states_list)
    with fc3:
        bands_list = ["All"] + sorted(all_customers["AGE_BAND"].dropna().unique().tolist())
        sel_band = st.selectbox("Age Band", bands_list)
    with fc4:
        nba_filter = st.selectbox("NBA Status", ["All", "Has Actions", "No Actions"])

    filtered = all_customers.copy()
    if search:
        filtered = filtered[
            filtered["FULL_NAME"].str.contains(search, case=False, na=False) |
            filtered["CUSTOMER_ID"].str.contains(search, case=False, na=False)
        ]
    if sel_state != "All":
        filtered = filtered[filtered["STATE_CODE"] == sel_state]
    if sel_band != "All":
        filtered = filtered[filtered["AGE_BAND"] == sel_band]
    if nba_filter != "All":
        filtered = filtered[filtered["NBA_STATUS"] == nba_filter]

    # Separate actioned vs pending
    pending = filtered[filtered["DECISION_STATUS"] == "Pending"]
    actioned = filtered[filtered["DECISION_STATUS"] == "Actioned"]

    actioned_count = len(actioned)
    if actioned_count > 0:
        st.caption(f"Showing {len(pending)} pending customers ({actioned_count} already actioned — shown below)")
    else:
        st.caption(f"Showing {len(pending)} customers")

    st.dataframe(pending, use_container_width=True, hide_index=True,
                 on_select="rerun", selection_mode="single-row", key="cust_table")

    if not actioned.empty:
        with st.expander(f"Actioned customers ({actioned_count})", expanded=False):
            st.dataframe(actioned, use_container_width=True, hide_index=True)

    sel = st.session_state.get("cust_table")
    if sel and sel.get("selection") and sel["selection"].get("rows"):
        idx = sel["selection"]["rows"][0]
        if idx < len(pending):
            chosen = pending.iloc[idx]
        else:
            st.stop()
        cust_id = chosen["CUSTOMER_ID"]

        with st.spinner("Loading full profile..."):
            profile = conn.query(
                "SELECT * FROM PROTECT360_DB.GOLD.VW_ADVISOR_CUSTOMER_360 WHERE CUSTOMER_ID = ?",
                params=[cust_id], ttl=timedelta(minutes=2),
            )

        if not profile.empty:
            p = profile.iloc[0]
            st.session_state.selected_customer_key = cust_id
            st.session_state.selected_customer_id = cust_id
            st.session_state.selected_customer_name = p["FULL_NAME"]

            with st.expander(f"📋 {p['FULL_NAME']} ({cust_id})", expanded=True):
                pc1, pc2, pc3 = st.columns(3)
                with pc1:
                    st.markdown("**Identity**")
                    st.markdown(f"- **Age:** {p['AGE']} ({p['AGE_BAND']})")
                    st.markdown(f"- **Gender:** {p['GENDER']}")
                    st.markdown(f"- **State:** {p['STATE_CODE']} — {p['POSTCODE']}")
                    st.markdown(f"- **Segment:** {p.get('SEGMENT_TYPE', 'N/A')}")
                with pc2:
                    st.markdown("**Policy**")
                    st.markdown(f"- **Active policies:** {int(p['ACTIVE_POLICY_COUNT'])}")
                    st.markdown(f"- **Coverage status:** {p.get('CURRENT_COVERAGE_STATUS', 'N/A')}")
                    st.markdown(f"- **Protection gap:** {'Yes' if p.get('PROTECTION_GAP_FLAG') else 'No'}")
                    st.markdown(f"- **Annual premium:** ${p['TOTAL_ANNUAL_PREMIUM']:,.0f}")
                with pc3:
                    st.markdown("**Risk**")
                    risk_colors = {"HIGH": "🔴", "MEDIUM": "🟡", "LOW": "🟢", None: "⚪"}
                    st.markdown(f"- **Vulnerability:** {risk_colors.get(p.get('VULNERABILITY_CLASS'),'⚪')} {p.get('VULNERABILITY_CLASS','N/A')}")
                    st.markdown(f"- **Vulnerability score:** {p.get('VULNERABILITY_MODEL_SCORE','N/A')}")
                    st.markdown(f"- **Top action score:** {p.get('TOP_ACTION_SCORE','N/A')}")
                    st.markdown(f"- **Capacity:** {p.get('CAPACITY_SCORE','N/A')}")
                    st.markdown(f"- **Income band:** {p.get('INCOME_BAND','N/A')}")

                dq = p["DATA_QUALITY_STATUS"]
                dq_colors = {"PASS": "green", "WARN": "orange", "FAIL": "red"}
                st.markdown(f"**Data Quality:** :{dq_colors.get(dq,'gray')}[{dq}]  |  **Completeness:** {p['DATA_COMPLETENESS_SCORE']}%")
                st.progress(min(float(p["DATA_COMPLETENESS_SCORE"]) / 100.0, 1.0))


# ═══════════════════════════════════════════════════════
# PAGE 3: RISK & PROPENSITY
# ═══════════════════════════════════════════════════════
elif page == "Risk & Propensity":
    st.markdown("<h1 style='color:#000;'>Risk & Propensity</h1>", unsafe_allow_html=True)

    cust_id = st.session_state.selected_customer_id
    if not cust_id:
        st.info("Select a customer from **Customer 360 Profile** to view details.")
        st.stop()

    st.markdown(f"**Customer:** {st.session_state.selected_customer_name} ({cust_id})")

    with st.spinner("Loading scores..."):
        scores = conn.query(
            "SELECT * FROM PROTECT360_DB.GOLD.VW_ADVISOR_CUSTOMER_360 WHERE CUSTOMER_ID = ?",
            params=[cust_id], ttl=timedelta(minutes=2),
        )

    if scores.empty:
        st.warning("No data found for this customer.")
        st.stop()

    s = scores.iloc[0]
    risk_colors = {"HIGH": "🔴", "MEDIUM": "🟡", "LOW": "🟢"}

    sc1, sc2 = st.columns(2)
    sc1.metric("Vulnerability Score", f"{s.get('VULNERABILITY_MODEL_SCORE', 'N/A')}",
               delta=f"{risk_colors.get(s.get('VULNERABILITY_CLASS',''),'⚪')} {s.get('VULNERABILITY_CLASS','N/A')}",
               delta_color="off", border=True)
    sc2.metric("Top Action Score", f"{s.get('TOP_ACTION_SCORE', 'N/A')}",
               delta=f"Capacity: {s.get('CAPACITY_SCORE', 'N/A')}",
               delta_color="off", border=True)

    # Model score factors
    with st.spinner("Loading score factors..."):
        ckey = conn.query(
            "SELECT CUSTOMER_KEY, EMPLOYMENT_TYPE_CODE FROM PROTECT360_DB.GOLD.CUSTOMER_360_PROFILE WHERE CUSTOMER_ID = ?",
            params=[cust_id], ttl=timedelta(minutes=5),
        )
    if ckey.empty:
        st.stop()
    customer_key = ckey.iloc[0]["CUSTOMER_KEY"]
    employment_type = ckey.iloc[0]["EMPLOYMENT_TYPE_CODE"]

    with st.spinner("Loading factors..."):
        factors = conn.query(
            """SELECT m.MODEL_NAME, f.FACTOR_NAME, f.FACTOR_VALUE, f.CONTRIBUTION,
                      f.DIRECTION, f.FACTOR_RANK, f.EXPLANATION
               FROM PROTECT360_DB.ML.MODEL_SCORE_FACTOR f
               JOIN PROTECT360_DB.ML.MODEL_SCORE s ON f.MODEL_SCORE_SK = s.MODEL_SCORE_SK
               JOIN PROTECT360_DB.ML.DIM_MODEL m ON s.MODEL_KEY = m.MODEL_KEY
               WHERE s.CUSTOMER_KEY = ?
               ORDER BY m.MODEL_NAME, f.FACTOR_RANK""",
            params=[customer_key], ttl=timedelta(minutes=5),
        )

    if not factors.empty:
        show_gig = True
        income_band = s.get('INCOME_BAND')
        if income_band == 'ABOVE_10L':
            show_gig = False
        if employment_type is not None and employment_type not in ('GIG_WORKER', 'DAILY_WAGE'):
            show_gig = False

        models = ["Vulnerability and Needs Score", "Government Scheme Eligibility"]
        model_labels = {
            "Vulnerability and Needs Score": "Vulnerability & Needs",
            "Government Scheme Eligibility": "Govt Scheme Eligibility",
            "Gig Worker Needs Score": "Gig Worker Needs",
        }
        if show_gig:
            models.append("Gig Worker Needs Score")

        fcols = st.columns(len(models))
        for i, model in enumerate(models):
            with fcols[i]:
                with st.container(border=True):
                    st.markdown(f"**{model_labels.get(model, model)} Factors**")
                    mf = factors[factors["MODEL_NAME"] == model]
                    for _, r in mf.iterrows():
                        arrow = "↑" if r["DIRECTION"] == "INCREASES_RISK" else "↓"
                        st.markdown(f"**{arrow} {r['FACTOR_NAME']}** = {r['FACTOR_VALUE']}  \nContribution: `{r['CONTRIBUTION']:.3f}`")
                        st.caption(r["EXPLANATION"])


# ═══════════════════════════════════════════════════════
# PAGE 4: NEXT BEST ACTION
# ═══════════════════════════════════════════════════════
elif page == "Next Best Action":
    st.markdown("<h1 style='color:#000;'>Next Best Action</h1>", unsafe_allow_html=True)

    # Show decision outcome if one was just recorded
    if "nba_decision_msg" in st.session_state and st.session_state.nba_decision_msg:
        msg_type, msg_text = st.session_state.nba_decision_msg
        if msg_type == "success":
            st.success(msg_text)
        elif msg_type == "error":
            st.error(msg_text)
        bc1, _ = st.columns([1, 3])
        if bc1.button("Select another customer", key="another_customer", type="primary"):
            st.session_state.nba_decision_msg = None
            st.session_state.nba_modify_mode = False
            if "cust_table" in st.session_state:
                del st.session_state["cust_table"]
            st.session_state.pending_nav = "Customer 360 Profile"
            st.rerun()
        st.stop()

    cust_id = st.session_state.selected_customer_id
    if not cust_id:
        st.info("Select a customer from **Customer 360 Profile** to view details.")
        st.stop()

    st.markdown(f"**Customer:** {st.session_state.selected_customer_name} ({cust_id})")

    # Initialize modify-mode session state
    if "nba_modify_mode" not in st.session_state:
        st.session_state.nba_modify_mode = False

    with st.spinner("Loading actions..."):
        ckey = conn.query(
            "SELECT CUSTOMER_KEY FROM PROTECT360_DB.GOLD.CUSTOMER_360_PROFILE WHERE CUSTOMER_ID = ?",
            params=[cust_id], ttl=timedelta(minutes=5),
        )
    if ckey.empty:
        st.stop()
    customer_key = ckey.iloc[0]["CUSTOMER_KEY"]

    with st.spinner("Loading NBA recommendations..."):
        nbas = conn.query(
            """SELECT nba.NEXT_BEST_ACTION_SK, nba.CUSTOMER_KEY, nba.ACTION_KEY, nba.PRIORITY_RANK,
                      nba.FINAL_ACTION_SCORE, nba.RECOMMENDED_CHANNEL, nba.REASON_TEXT,
                      nba.ADVISOR_MESSAGE, nba.ACTION_EXPIRY_TS, nba.HUMAN_REVIEW_REQUIRED,
                      cat.ACTION_NAME, cat.ACTION_CATEGORY
               FROM PROTECT360_DB.GOLD.NEXT_BEST_ACTION nba
               JOIN PROTECT360_DB.GOLD.NBA_ACTION_CATALOG cat ON nba.ACTION_KEY = cat.ACTION_KEY
               WHERE nba.CUSTOMER_KEY = ?
               ORDER BY nba.PRIORITY_RANK""",
            params=[customer_key], ttl=timedelta(minutes=2),
        )

    if nbas.empty:
        st.warning("No eligible actions for this customer.")

        # Show why there are no actions
        with st.expander("Why are there no actions?", expanded=True):
            suppression_info = conn.query(
                """SELECT c.ACTION_KEY, cat.ACTION_NAME,
                          CASE WHEN c.ELIGIBLE_FLAG THEN 'True' ELSE 'False' END AS IS_ELIGIBLE,
                          c.SUPPRESSION_REASON_CODE, c.FINAL_ACTION_SCORE
                   FROM PROTECT360_DB.GOLD.NBA_ACTION_CANDIDATE c
                   JOIN PROTECT360_DB.GOLD.NBA_ACTION_CATALOG cat ON c.ACTION_KEY = cat.ACTION_KEY
                   WHERE c.CUSTOMER_KEY = ?
                   ORDER BY c.ACTION_KEY""",
                params=[customer_key], ttl=timedelta(minutes=2),
            )
            if not suppression_info.empty:
                st.markdown("All action candidates were filtered out by the NBA decision engine:")
                st.dataframe(suppression_info, use_container_width=True, hide_index=True)

                reasons = suppression_info["SUPPRESSION_REASON_CODE"].dropna().unique().tolist()
                if "NO_CONSENT" in reasons:
                    st.info("This customer has not provided marketing consent. "
                            "Insurance and education actions require consent before contact. "
                            "Community referrals (CSR, Financial Counselling) are evaluated independently "
                            "but this customer does not meet the eligibility criteria for those either.")
                elif "NOT_ELIGIBLE" in reasons:
                    st.info("This customer does not meet the eligibility criteria for any action "
                            "in the current action catalogue.")
            else:
                st.caption("No candidate records found for this customer.")
        st.stop()

    channel_icons = {"PHONE": "📞", "EMAIL": "📧", "APP": "📱", "ADVISOR_CALL": "👤"}
    cat_colors = {"INSURANCE": "blue", "COMMUNITY": "violet", "EDUCATION": "green"}
    session = conn.session()

    for _, a in nbas.iterrows():
        with st.container(border=True):
            hc1, hc2 = st.columns([3, 1])
            with hc1:
                cat_c = cat_colors.get(a["ACTION_CATEGORY"], "gray")
                st.markdown(f"### Rank {int(a['PRIORITY_RANK'])}: {a['ACTION_NAME']}")
                st.markdown(f":{cat_c}[{a['ACTION_CATEGORY']}]  |  "
                            f"{channel_icons.get(a['RECOMMENDED_CHANNEL'], '📋')} {a['RECOMMENDED_CHANNEL']}  |  "
                            f"{'🔴 Human Review Required' if a['HUMAN_REVIEW_REQUIRED'] else '🟢 Auto-eligible'}")
            with hc2:
                st.metric("Score", f"{a['FINAL_ACTION_SCORE']:.2%}", border=True)

            st.markdown(f"*{a['REASON_TEXT']}*")
            st.info(a["ADVISOR_MESSAGE"])
            st.caption(f"Expires: {a['ACTION_EXPIRY_TS']}")

            # Decision buttons for rank 1 only — inside the card
            if int(a["PRIORITY_RANK"]) == 1:
                nba_sk = a["NEXT_BEST_ACTION_SK"]
                st.divider()
                bc1, bc2, bc3, _ = st.columns([1, 1, 1, 3])

                if bc1.button("✅ Accept", key=f"accept_{nba_sk}"):
                    session.sql(
                        """INSERT INTO PROTECT360_DB.GOLD.ACTION_OUTCOME
                           (ACTION_OUTCOME_SK, NEXT_BEST_ACTION_SK, CUSTOMER_KEY, ADVISOR_DECISION,
                            OUTCOME_RECORDED_TS, FOLLOW_UP_REQUIRED)
                           SELECT MD5(? || CURRENT_TIMESTAMP()::STRING),
                                  ?, ?, 'ACCEPTED', CURRENT_TIMESTAMP(), FALSE""",
                        params=[nba_sk, nba_sk, customer_key],
                    ).collect()
                    st.session_state.nba_decision_msg = ("success", f"Decision **ACCEPTED** recorded for {st.session_state.selected_customer_name}.")
                    st.session_state.selected_customer_key = None
                    st.session_state.selected_customer_id = None
                    st.session_state.selected_customer_name = None
                    st.rerun()

                if bc2.button("❌ Reject", key=f"reject_{nba_sk}"):
                    session.sql(
                        """INSERT INTO PROTECT360_DB.GOLD.ACTION_OUTCOME
                           (ACTION_OUTCOME_SK, NEXT_BEST_ACTION_SK, CUSTOMER_KEY, ADVISOR_DECISION,
                            OUTCOME_RECORDED_TS, FOLLOW_UP_REQUIRED)
                           SELECT MD5(? || CURRENT_TIMESTAMP()::STRING),
                                  ?, ?, 'REJECTED', CURRENT_TIMESTAMP(), TRUE""",
                        params=[nba_sk, nba_sk, customer_key],
                    ).collect()
                    st.session_state.nba_decision_msg = ("error", f"Decision **REJECTED** recorded for {st.session_state.selected_customer_name}.")
                    st.session_state.selected_customer_key = None
                    st.session_state.selected_customer_id = None
                    st.session_state.selected_customer_name = None
                    st.rerun()

                if bc3.button("✏️ Modify", key=f"modify_{nba_sk}"):
                    st.session_state.nba_modify_mode = True

    # Modify mode: show all action candidates for this customer
    if st.session_state.nba_modify_mode:
        st.divider()
        with st.container(border=True):
            st.subheader("Select an Alternative Action")
            st.caption("Choose one eligible action to replace the current recommendation.")

            with st.spinner("Loading all action candidates..."):
                all_candidates = conn.query(
                    """SELECT c.ACTION_KEY, cat.ACTION_NAME, cat.ACTION_CATEGORY,
                              CASE WHEN c.ELIGIBLE_FLAG THEN 'True' ELSE 'False' END AS IS_ELIGIBLE,
                              c.SUPPRESSION_REASON_CODE,
                              c.FINAL_ACTION_SCORE
                       FROM PROTECT360_DB.GOLD.NBA_ACTION_CANDIDATE c
                       JOIN PROTECT360_DB.GOLD.NBA_ACTION_CATALOG cat ON c.ACTION_KEY = cat.ACTION_KEY
                       WHERE c.CUSTOMER_KEY = ?
                       ORDER BY c.FINAL_ACTION_SCORE DESC""",
                    params=[customer_key], ttl=timedelta(minutes=2),
                )

            if all_candidates.empty:
                st.caption("No action candidates found for this customer.")
            else:
                st.dataframe(all_candidates, use_container_width=True, hide_index=True)

                eligible = all_candidates[all_candidates["IS_ELIGIBLE"] == "True"]
                if eligible.empty:
                    st.warning("No eligible actions available for this customer.")
                else:
                    action_options = {
                        f"{r['ACTION_NAME']} ({r['ACTION_CATEGORY']}) — Score: {r['FINAL_ACTION_SCORE']:.4f}": r['ACTION_KEY']
                        for _, r in eligible.iterrows()
                    }
                    selected_label = st.radio(
                        "Select an eligible action:",
                        list(action_options.keys()),
                        key="modify_action_radio",
                    )
                    selected_action_key = action_options[selected_label]

                    mc1, mc2, _ = st.columns([1, 1, 4])
                    if mc1.button("Confirm Modification", key="confirm_modify", type="primary"):
                        session.sql(
                            """INSERT INTO PROTECT360_DB.GOLD.ACTION_OUTCOME
                               (ACTION_OUTCOME_SK, NEXT_BEST_ACTION_SK, CUSTOMER_KEY, ADVISOR_DECISION,
                                ADVISOR_FEEDBACK, OUTCOME_RECORDED_TS, FOLLOW_UP_REQUIRED)
                               SELECT MD5(? || ? || CURRENT_TIMESTAMP()::STRING),
                                      ?, ?, 'MODIFIED',
                                      'Advisor overrode to action: ' || ?,
                                      CURRENT_TIMESTAMP(), TRUE""",
                            params=[customer_key, selected_action_key,
                                    nbas.iloc[0]["NEXT_BEST_ACTION_SK"], customer_key,
                                    selected_action_key],
                        ).collect()
                        selected_name = selected_label.split(" (")[0]
                        st.session_state.nba_decision_msg = ("success", f"Action modified to **{selected_name}** for {st.session_state.selected_customer_name}.")
                        st.session_state.nba_modify_mode = False
                        st.session_state.selected_customer_key = None
                        st.session_state.selected_customer_id = None
                        st.session_state.selected_customer_name = None
                        st.rerun()

                    if mc2.button("Cancel", key="cancel_modify"):
                        st.session_state.nba_modify_mode = False
                        st.rerun()


# ═══════════════════════════════════════════════════════
# PAGE 5: GOVERNANCE MONITOR
# ═══════════════════════════════════════════════════════
elif page == "Governance Monitor":
    st.markdown("<h1 style='color:#000;'>Governance Monitor</h1>", unsafe_allow_html=True)

    with st.spinner("Loading governance metrics..."):
        gov = conn.query("SELECT * FROM PROTECT360_DB.GOLD.VW_GOVERNANCE_MONITOR", ttl=timedelta(minutes=5))

    if gov.empty:
        st.warning("No governance data available.")
        st.stop()

    g = gov.iloc[0]

    with st.spinner("Loading score coverage..."):
        score_cov = conn.query("""
            SELECT ROUND(COUNT(DISTINCT CUSTOMER_KEY) * 100.0 /
                   (SELECT COUNT(*) FROM PROTECT360_DB.GOLD.CUSTOMER_360_PROFILE), 1) AS SCORE_COVERAGE_PCT
            FROM PROTECT360_DB.ML.MODEL_SCORE
        """, ttl=timedelta(minutes=5))
    score_pct = score_cov.iloc[0]["SCORE_COVERAGE_PCT"] if not score_cov.empty else 0

    gc1, gc2, gc3 = st.columns(3)
    gc1.metric("DQ Pass Rate", f"{g['DQ_GREEN_RATE_PCT']}%",
               delta=f"{int(g['DQ_GREEN_COUNT'])} / {int(g['TOTAL_PROFILES'])}", delta_color="off", border=True)
    gc2.metric("Marketing Consent", f"{g['MARKETING_CONSENT_RATE_PCT']}%",
               delta=f"{int(g['MARKETING_CONSENT_COUNT'])} customers", delta_color="off", border=True)
    gc3.metric("Score Coverage", f"{score_pct}%",
               delta=f"ML models scored", delta_color="off", border=True)

    gc4, gc5, gc6 = st.columns(3)
    with gc4:
        with st.container(border=True):
            st.subheader("Data Quality Distribution")
            with st.spinner("Loading DQ breakdown..."):
                dq = conn.query("""
                    SELECT DQ_STATUS AS STATUS, COUNT(*) AS COUNT
                    FROM PROTECT360_DB.GOLD.CUSTOMER_360_PROFILE
                    GROUP BY 1
                """, ttl=timedelta(minutes=5))
            import altair as alt
            pie = alt.Chart(dq).mark_arc(innerRadius=40).encode(
                theta=alt.Theta("COUNT:Q"),
                color=alt.Color("STATUS:N", scale=alt.Scale(
                    domain=["GREEN", "AMBER", "RED"],
                    range=["#2ecc71", "#f39c12", "#e74c3c"])),
                tooltip=["STATUS", "COUNT"],
            ).properties(height=280)
            st.altair_chart(pie, use_container_width=True)

    with gc5:
        with st.container(border=True):
            st.subheader("NBA Decision Outcomes")
            with st.spinner("Loading decision outcomes..."):
                outcomes = conn.query("""
                    SELECT ADVISOR_DECISION AS DECISION, COUNT(*) AS COUNT
                    FROM PROTECT360_DB.GOLD.ACTION_OUTCOME
                    GROUP BY 1
                """, ttl=timedelta(seconds=30))
            if outcomes.empty:
                st.caption("No advisor decisions recorded yet.")
            else:
                pie2 = alt.Chart(outcomes).mark_arc(innerRadius=40).encode(
                    theta=alt.Theta("COUNT:Q"),
                    color=alt.Color("DECISION:N", scale=alt.Scale(
                        domain=["ACCEPTED", "REJECTED", "MODIFIED"],
                        range=["#2ecc71", "#e74c3c", "#3498db"])),
                    tooltip=["DECISION", "COUNT"],
                ).properties(height=280)
                st.altair_chart(pie2, use_container_width=True)

    with gc6:
        with st.container(border=True):
            st.subheader("Consent Rates")
            with st.spinner("Loading consent data..."):
                consent = conn.query("""
                    SELECT 'Marketing — Yes' AS STATUS,
                           COUNT_IF(MARKETING_CONSENT_FLAG) AS COUNT
                    FROM PROTECT360_DB.GOLD.CUSTOMER_360_PROFILE
                    UNION ALL
                    SELECT 'Marketing — No',
                           COUNT_IF(NOT MARKETING_CONSENT_FLAG OR MARKETING_CONSENT_FLAG IS NULL)
                    FROM PROTECT360_DB.GOLD.CUSTOMER_360_PROFILE
                    UNION ALL
                    SELECT 'Health Data — Yes',
                           COUNT_IF(HEALTH_DATA_CONSENT_FLAG)
                    FROM PROTECT360_DB.GOLD.CUSTOMER_360_PROFILE
                    UNION ALL
                    SELECT 'Health Data — No',
                           COUNT_IF(NOT HEALTH_DATA_CONSENT_FLAG OR HEALTH_DATA_CONSENT_FLAG IS NULL)
                    FROM PROTECT360_DB.GOLD.CUSTOMER_360_PROFILE
                """, ttl=timedelta(minutes=5))
            consent_pie = alt.Chart(consent).mark_arc(innerRadius=40).encode(
                theta=alt.Theta("COUNT:Q"),
                color=alt.Color("STATUS:N", scale=alt.Scale(
                    domain=["Marketing — Yes", "Marketing — No", "Health Data — Yes", "Health Data — No"],
                    range=["#FFCC00", "#f5e6a3", "#3498db", "#aed6f1"])),
                tooltip=["STATUS", "COUNT"],
            ).properties(height=280)
            st.altair_chart(consent_pie, use_container_width=True)

    with st.container(border=True):
        st.subheader("Recent Advisor Decisions")
        with st.spinner("Loading decisions..."):
            decisions = conn.query("""
                SELECT CUSTOMER_KEY, ADVISOR_DECISION, OUTCOME_RECORDED_TS,
                       CASE WHEN FOLLOW_UP_REQUIRED THEN 'Yes' ELSE 'No' END AS FOLLOW_UP_REQUIRED
                FROM PROTECT360_DB.GOLD.ACTION_OUTCOME
                ORDER BY OUTCOME_RECORDED_TS DESC
                LIMIT 20
            """, ttl=timedelta(seconds=30))
        if decisions.empty:
            st.caption("No advisor decisions recorded yet.")
        else:
            st.dataframe(decisions, use_container_width=True, hide_index=True)

    with st.container(border=True):
        st.subheader("Model Score Coverage")
        with st.spinner("Loading model coverage..."):
            coverage = conn.query("""
                SELECT m.MODEL_NAME, s.SCORE_CLASS, COUNT(*) AS CUSTOMERS
                FROM PROTECT360_DB.ML.MODEL_SCORE s
                JOIN PROTECT360_DB.ML.DIM_MODEL m ON s.MODEL_KEY = m.MODEL_KEY
                GROUP BY 1, 2 ORDER BY 1, 2
            """, ttl=timedelta(minutes=5))
        st.dataframe(coverage, use_container_width=True, hide_index=True)
