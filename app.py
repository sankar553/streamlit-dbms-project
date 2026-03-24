"""
app.py — Streamlit Frontend
============================
Secure Clinical Summary View Generator
MongoDB + PyMongo + Streamlit

Run: streamlit run app.py
"""

import streamlit as st
import pandas as pd
from database import (
    seed_data,
    get_patients_by_role,
    search_patient_by_id,
    update_patient_disease,
    log_access,
    get_access_logs,
    get_disease_summary,
    get_age_stats,
    get_database,
)

# ================================================================
# ① PAGE CONFIG
# ================================================================

st.set_page_config(
    page_title="Secure Clinical Summary",
    page_icon="🏥",
    layout="wide",
)

# ================================================================
# ② ROLE → USER MAPPING
# ================================================================

ROLE_USER_MAP = {
    "Doctor":     {"user_id": 1, "username": "dr_adams",    "role": "doctor"},
    "Researcher": {"user_id": 3, "username": "res_smith",   "role": "researcher"},
    "Admin":      {"user_id": 4, "username": "admin_jones", "role": "admin"},
}

ROLE_INFO = {
    "doctor":     "✅ Full patient data visible\n✅ Name, phone, address\n✅ All medical details",
    "researcher": "🔒 Name → ANONYMIZED\n🔒 Phone → HIDDEN\n🔒 Address → HIDDEN\n✅ Age + Disease",
    "admin":      "🔒 Name → RESTRICTED\n🔒 Phone → RESTRICTED\n🔒 Address → RESTRICTED\n✅ Age + Disease",
}

# ================================================================
# ③ INIT DB (seed once per session)
# ================================================================

@st.cache_data(show_spinner=False)
def initialize() -> dict:
    return seed_data()

with st.spinner("🔗 Connecting to MongoDB Atlas …"):
    try:
        seed_status = initialize()
        db_ok = True
    except Exception as e:
        st.error(f"❌ MongoDB connection failed: {e}")
        st.stop()

# ================================================================
# ④ TITLE
# ================================================================

st.title("🏥 Secure Clinical Summary View Generator")
st.caption("DBMS Mini Project · MongoDB Atlas · PyMongo · Streamlit · RBAC")
st.divider()

# ================================================================
# ⑤ SIDEBAR
# ================================================================

with st.sidebar:
    st.header("⚙️ Control Panel")

    selected_label = st.selectbox(
        "Select Role",
        options=list(ROLE_USER_MAP.keys()),
        help="Each role has a different level of access to patient data.",
    )
    user_info = ROLE_USER_MAP[selected_label]
    role      = str(user_info["role"])
    user_id   = int(user_info["user_id"])
    username  = str(user_info["username"])

    st.info(
        f"**User:** `{username}`\n\n"
        f"**Role:** `{role}`\n\n"
        + ROLE_INFO[role]
    )

    generate_btn = st.button("🔍 Generate Summary", use_container_width=True, type="primary")

    st.divider()
    st.subheader("🔎 Search Patient")
    search_id  = st.number_input("Patient ID", min_value=1, max_value=1000, step=1, value=1)
    search_btn = st.button("Search", use_container_width=True)

    st.divider()
    st.subheader("✏️ Update Patient Disease")
    with st.form("update_form"):
        upd_pid     = st.number_input("Patient ID to update", min_value=1, step=1, value=1)
        upd_disease = st.text_input("New Disease", placeholder="e.g. Pneumonia")
        upd_btn     = st.form_submit_button("Update", use_container_width=True)

    st.divider()
    st.caption("DB Seed Status")
    for col, msg in seed_status.items():
        st.caption(f"• **{col}**: {msg}")

# ================================================================
# ⑥ MAIN TABS
# ================================================================

tab_summary, tab_mongo, tab_agg, tab_log = st.tabs([
    "📋 Patient Summary",
    "🍃 MongoDB Queries",
    "📊 Dashboard & Aggregation",
    "📜 Access Logs",
])

# ─────────────────────────────────────────────────────────────
# TAB 1 — Patient Summary
# ─────────────────────────────────────────────────────────────
with tab_summary:
    st.subheader(f"Patient Summary — {selected_label} View")

    # ── Generate Summary ──────────────────────────────────────
    if generate_btn:
        with st.spinner("Fetching data from MongoDB …"):
            patients = get_patients_by_role(role)
            # Log access for every patient (insertOne per patient)
            for p in patients:
                log_access(user_id, username, p["patient_id"],
                           f"Summary generated as {role}")

        if patients:
            df = pd.DataFrame(patients)

            # Metrics
            c1, c2, c3 = st.columns(3)
            c1.metric("Records Returned", len(df))
            c2.metric("Fields Visible",   len(df.columns))
            c3.metric("Access Role",      role.capitalize())

            st.dataframe(df, use_container_width=True, hide_index=True)
            st.success(f"✅ Summary generated for **{selected_label}**. Access logged.")
        else:
            st.warning("No patient records found in the database.")

    # ── Search Patient ────────────────────────────────────────
    elif search_btn:
        result = search_patient_by_id(search_id, role)
        log_access(user_id, username, search_id,
                   f"Patient search by {username} [{role}]")

        if result:
            st.subheader(f"🔎 Search Result — Patient ID: {search_id}")
            st.dataframe(pd.DataFrame([result]), use_container_width=True, hide_index=True)
        else:
            st.warning(f"No patient found with ID **{search_id}**.")

    # ── Update Patient ────────────────────────────────────────
    elif upd_btn:
        if role != "doctor":
            st.error("🚫 Only Doctors are authorised to update patient records.")
        elif upd_disease.strip():
            ok = update_patient_disease(upd_pid, upd_disease.strip())
            if ok:
                log_access(user_id, username, upd_pid,
                           f"Updated disease to '{upd_disease}' by {username}")
                st.success(f"✅ Patient {upd_pid} disease updated to **{upd_disease}**.")
            else:
                st.warning(f"Patient ID {upd_pid} not found.")
        else:
            st.warning("Please enter a new disease name.")

    else:
        st.info("👈 Select your **Role** from the sidebar and click **Generate Summary**.")

# ─────────────────────────────────────────────────────────────
# TAB 2 — MongoDB Queries
# ─────────────────────────────────────────────────────────────
with tab_mongo:
    st.subheader("MongoDB Operations Reference")

    st.markdown("#### 🟢 insertOne() — Add a patient")
    st.code("""db.patients.insert_one({
    "patient_id": 6,
    "name":       "New Patient",
    "age":        30,
    "disease":    "Flu",
    "phone":      "9000000001",
    "address":    "New City"
})""", language="python")

    st.markdown("#### 🔵 find() — Fetch all patients (Doctor view)")
    st.code("""# Fetch all patients, exclude MongoDB _id
db.patients.find({}, {"_id": 0})""", language="python")

    st.markdown("#### 🟡 find() with filter — Search by ID")
    st.code("""db.patients.find_one({"patient_id": 3}, {"_id": 0})""", language="python")

    st.markdown("#### 🟠 updateOne() — Update disease")
    st.code("""db.patients.update_one(
    {"patient_id": 3},               # filter
    {"$set": {"disease": "Flu"}}     # update
)""", language="python")

    st.markdown("#### 🟣 aggregate() — Disease count summary")
    st.code("""db.patients.aggregate([
    {"$group":   {"_id": "$disease", "count": {"$sum": 1}}},
    {"$sort":    {"count": -1}},
    {"$project": {"_id": 0, "disease": "$_id", "patient_count": "$count"}}
])""", language="python")

    st.markdown("#### 🔴 aggregate() — Access logs with sort + limit")
    st.code("""db.access_logs.aggregate([
    {"$sort":    {"timestamp": -1}},
    {"$limit":   20},
    {"$project": {"_id": 0, "log_id": 1, "username": 1,
                  "patient_id": 1, "purpose": 1, "timestamp": 1}}
])""", language="python")

    st.markdown("#### 🔒 Anonymization Logic (Researcher role)")
    st.code("""# Applied in Python after find()
if role == "researcher":
    doc["name"]    = "*** ANONYMIZED ***"
    doc["phone"]   = "*** HIDDEN ***"
    doc["address"] = "*** HIDDEN ***"
""", language="python")

    st.markdown("#### 📋 Collection Schema (data model)")
    col1, col2, col3 = st.columns(3)
    with col1:
        st.markdown("**patients**")
        st.code("""{
  patient_id: int,
  name:       str,
  age:        int,
  disease:    str,
  phone:      str,
  address:    str
}""")
    with col2:
        st.markdown("**users**")
        st.code("""{
  user_id:  int,
  username: str,
  role:     str
  # doctor | researcher | admin
}""")
    with col3:
        st.markdown("**access_logs**")
        st.code("""{
  log_id:     int,
  user_id:    int,
  username:   str,
  patient_id: int,
  purpose:    str,
  timestamp:  datetime
}""")

# ─────────────────────────────────────────────────────────────
# TAB 3 — Dashboard & Aggregation Metrics
# ─────────────────────────────────────────────────────────────
with tab_agg:
    st.subheader("📊 Dashboard Metrics (Aggregation Pipelines)")

    # ── Age stats ─────────────────────────────────────────────
    age_stats = get_age_stats()
    if age_stats:
        a1, a2, a3, a4 = st.columns(4)
        a1.metric("Avg Age", f"{age_stats.get('avg_age', 0):.1f}")
        a2.metric("Min Age", int(age_stats.get("min_age", 0)))
        a3.metric("Max Age", int(age_stats.get("max_age", 0)))
        db = get_database()
        a4.metric("Total Patients", db.patients.count_documents({}))

    st.divider()

    # ── Disease summary chart ─────────────────────────────────
    st.subheader("Disease Distribution")
    disease_data = get_disease_summary()
    if disease_data:
        df_disease = pd.DataFrame(disease_data)
        st.bar_chart(df_disease.set_index("disease")["patient_count"])
        st.dataframe(df_disease, use_container_width=True, hide_index=True)

    st.divider()

    # ── Total access logs count ───────────────────────────────
    st.subheader("Access Log Metrics")
    db   = get_database()
    logs = list(db.access_logs.aggregate([
        {"$group": {"_id": "$username", "access_count": {"$sum": 1}}},
        {"$sort":  {"access_count": -1}},
        {"$project": {"_id": 0, "username": "$_id", "access_count": 1}},
    ]))
    if logs:
        df_logs = pd.DataFrame(logs)
        st.dataframe(df_logs, use_container_width=True, hide_index=True)
    else:
        st.info("No access logs yet. Generate a summary first.")

# ─────────────────────────────────────────────────────────────
# TAB 4 — Access Log Viewer
# ─────────────────────────────────────────────────────────────
with tab_log:
    st.subheader("📜 Access Logs — Audit Trail")
    st.caption("Every data access is logged via `db.access_logs.insert_one()`.")

    if st.button("🔄 Refresh Logs"):
        st.rerun()

    logs_raw = get_access_logs(limit=50)
    if logs_raw:
        # Format timestamp
        for entry in logs_raw:
            ts = entry.get("timestamp")
            if ts:
                # split off microseconds/tz, replace T separator
                entry["timestamp"] = str(ts).replace("T", " ").split(".")[0].split("+")[0]

        df_audit = pd.DataFrame(logs_raw)

        l1, l2, l3 = st.columns(3)
        l1.metric("Total Entries",    len(df_audit))
        l2.metric("Unique Users",     df_audit["username"].nunique()   if "username"   in df_audit else "—")
        l3.metric("Unique Patients",  df_audit["patient_id"].nunique() if "patient_id" in df_audit else "—")

        st.dataframe(df_audit, use_container_width=True, hide_index=True)
    else:
        st.info("No logs yet. Click **Generate Summary** to create log entries.")

# ── Footer ──────────────────────────────────────────────────
st.divider()
st.caption(
    "Secure Clinical Summary View Generator · MongoDB Atlas · PyMongo · Streamlit · RBAC"
)
