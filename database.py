"""
database.py — MongoDB Backend
==============================
Secure Clinical Summary View Generator
Connects to MongoDB Atlas and handles all CRUD + aggregation operations.

Collections:
  • patients     — patient records
  • users        — system users with roles
  • access_logs  — audit trail of every data access
"""

from pymongo import MongoClient, DESCENDING
from datetime import datetime, timezone
import streamlit as st

# ================================================================
# ① CONNECTION
# ================================================================

# MongoDB Atlas connection string
# NOTE: The '@' in the password is URL-encoded as '%40'
MONGO_URI = "mongodb+srv://Sankar:Sankar%4007@dbms.1e3vof9.mongodb.net/?appName=dbms"
DB_NAME   = "clinical_db"


@st.cache_resource(show_spinner=False)
def get_database():
    """
    Create and cache one MongoClient for the entire Streamlit session.
    Returns the clinical_db database object.
    """
    client = MongoClient(
        MONGO_URI,
        serverSelectionTimeoutMS=8000,
        tls=True,
        tlsAllowInvalidCertificates=True,   # bypasses SSL date check (dev environment)
    )
    return client[DB_NAME]


# ================================================================
# ② SEED / INITIALISE DATA
# ================================================================

SAMPLE_PATIENTS = [
    {"patient_id": 1, "name": "John Doe",      "age": 45, "disease": "Hypertension",
     "phone": "9876543210", "address": "12 Oak Street, Delhi"},
    {"patient_id": 2, "name": "Jane Smith",     "age": 32, "disease": "Asthma",
     "phone": "9123456789", "address": "45 Rose Avenue, Mumbai"},
    {"patient_id": 3, "name": "Alice Brown",    "age": 28, "disease": "Type 2 Diabetes",
     "phone": "9988776655", "address": "78 Elm Road, Bangalore"},
    {"patient_id": 4, "name": "Bob Johnson",    "age": 50, "disease": "Coronary Artery Disease",
     "phone": "9871234560", "address": "23 Pine Lane, Chennai"},
    {"patient_id": 5, "name": "Carlos Reyes",   "age": 38, "disease": "Migraine",
     "phone": "9112233445", "address": "56 Cedar Blvd, Hyderabad"},
]

SAMPLE_USERS = [
    {"user_id": 1, "username": "dr_adams",    "role": "doctor"},
    {"user_id": 2, "username": "dr_baker",    "role": "doctor"},
    {"user_id": 3, "username": "res_smith",   "role": "researcher"},
    {"user_id": 4, "username": "admin_jones", "role": "admin"},
]


def seed_data() -> dict:
    """
    Insert sample data if collections are empty.
    Uses insertOne-style logic (insert_one per doc for demonstration).
    Returns a status dict for the UI to display.
    """
    db     = get_database()
    status = {}

    # ── patients ────────────────────────────────────
    if db.patients.count_documents({}) == 0:
        for doc in SAMPLE_PATIENTS:
            db.patients.insert_one(doc.copy())    # insertOne()
        status["patients"] = f"Inserted {len(SAMPLE_PATIENTS)} patients"
    else:
        status["patients"] = f"Already has {db.patients.count_documents({})} patients"

    # ── users ────────────────────────────────────────
    if db.users.count_documents({}) == 0:
        for doc in SAMPLE_USERS:
            db.users.insert_one(doc.copy())        # insertOne()
        status["users"] = f"Inserted {len(SAMPLE_USERS)} users"
    else:
        status["users"] = f"Already has {db.users.count_documents({})} users"

    return status


# ================================================================
# ③ ROLE-BASED DATA FETCH  (find() + Python-level anonymization)
# ================================================================

def get_patients_by_role(role: str) -> list[dict]:
    """
    Fetch all patients from MongoDB and apply role-based filtering.

    Operations used:
      • db.patients.find({})  →  retrieve all documents
      • Python post-processing  →  mask fields based on role

    Role access levels:
      doctor      → full data
      researcher  → name / phone / address masked
      admin       → name / phone / address restricted
    """
    db   = get_database()
    docs = list(db.patients.find({}, {"_id": 0}))   # find() — exclude _id

    results = []
    for doc in docs:
        if role == "doctor":
            # Full data — no masking
            results.append({
                "patient_id": doc["patient_id"],
                "name":       doc["name"],
                "age":        doc["age"],
                "disease":    doc["disease"],
                "phone":      doc["phone"],
                "address":    doc["address"],
            })
        elif role == "researcher":
            # Anonymized — hide PII
            results.append({
                "patient_id": doc["patient_id"],
                "name":       "*** ANONYMIZED ***",
                "age":        doc["age"],
                "disease":    doc["disease"],
                "phone":      "*** HIDDEN ***",
                "address":    "*** HIDDEN ***",
            })
        elif role == "admin":
            # Limited — only ID, age, disease
            results.append({
                "patient_id": doc["patient_id"],
                "name":       "*** RESTRICTED ***",
                "age":        doc["age"],
                "disease":    doc["disease"],
                "phone":      "*** RESTRICTED ***",
                "address":    "*** RESTRICTED ***",
            })

    return results


# ================================================================
# ④ SEARCH  (find() with filter)
# ================================================================

def search_patient_by_id(patient_id: int, role: str) -> dict | None:
    """
    Search a single patient by patient_id and apply role masking.
    MongoDB operation: db.patients.find_one({"patient_id": patient_id})
    """
    db  = get_database()
    doc = db.patients.find_one({"patient_id": patient_id}, {"_id": 0})
    if not doc:
        return None

    if role == "researcher":
        doc["name"]    = "*** ANONYMIZED ***"
        doc["phone"]   = "*** HIDDEN ***"
        doc["address"] = "*** HIDDEN ***"
    elif role == "admin":
        doc["name"]    = "*** RESTRICTED ***"
        doc["phone"]   = "*** RESTRICTED ***"
        doc["address"] = "*** RESTRICTED ***"

    return doc


# ================================================================
# ⑤ UPDATE  (updateOne)
# ================================================================

def update_patient_disease(patient_id: int, new_disease: str) -> bool:
    """
    Update a patient's disease field.
    MongoDB operation: db.patients.update_one(filter, {'$set': update})
    """
    db     = get_database()
    result = db.patients.update_one(
        {"patient_id": patient_id},          # filter
        {"$set": {"disease": new_disease}}   # update
    )
    return result.modified_count > 0


# ================================================================
# ⑥ ACCESS LOGGING  (insertOne into access_logs)
# ================================================================

def log_access(user_id: int, username: str, patient_id: int | str, purpose: str) -> None:
    """
    Log an access event into the access_logs collection.
    MongoDB operation: db.access_logs.insert_one(doc)
    """
    db = get_database()
    next_id = db.access_logs.count_documents({}) + 1
    db.access_logs.insert_one({
        "log_id":     next_id,
        "user_id":    user_id,
        "username":   username,
        "patient_id": patient_id,
        "purpose":    purpose,
        "timestamp":  datetime.now(timezone.utc),
    })


# ================================================================
# ⑦ AGGREGATION PIPELINE
# ================================================================

def get_access_logs(limit: int = 50) -> list[dict]:
    """
    Fetch access logs sorted by timestamp.
    MongoDB operation: db.access_logs.aggregate([...])

    Pipeline stages:
      $sort      → newest first
      $limit     → cap at limit rows
      $project   → reshape for display
    """
    db = get_database()
    pipeline = [
        {"$sort":    {"timestamp": DESCENDING}},        # sort newest first
        {"$limit":   limit},                            # cap results
        {"$project": {                                  # reshape output
            "_id":        0,
            "log_id":     1,
            "username":   1,
            "patient_id": 1,
            "purpose":    1,
            "timestamp":  1,
        }},
    ]
    return list(db.access_logs.aggregate(pipeline))


def get_disease_summary() -> list[dict]:
    """
    Aggregate patient count per disease.
    MongoDB operation: db.patients.aggregate([grouping pipeline])
    """
    db = get_database()
    pipeline = [
        {"$group": {"_id": "$disease", "count": {"$sum": 1}}},
        {"$sort":  {"count": DESCENDING}},
        {"$project": {"_id": 0, "disease": "$_id", "patient_count": "$count"}},
    ]
    return list(db.patients.aggregate(pipeline))


def get_age_stats() -> dict:
    """
    Compute min / max / avg age using aggregation.
    MongoDB operation: db.patients.aggregate([stats pipeline])
    """
    db = get_database()
    pipeline = [
        {"$group": {
            "_id":     None,
            "avg_age": {"$avg": "$age"},
            "min_age": {"$min": "$age"},
            "max_age": {"$max": "$age"},
        }}
    ]
    result = list(db.patients.aggregate(pipeline))
    return result[0] if result else {}
