from datetime import datetime
from typing import Optional, List
from bson import ObjectId

from db.mongo import get_db
from db.models import StageEnum, StageProgress


def _id(doc: dict) -> dict:
    doc["id"] = str(doc.pop("_id"))
    return doc


# ══════════════════════════════════════════════════════════════════════════════
# STEP 1 — Users
# ══════════════════════════════════════════════════════════════════════════════

async def user_create(name, email, password_hash, phone=None) -> dict:
    db = get_db()
    doc = {
        "name":          name,
        "email":         email,
        "password_hash": password_hash,
        "phone":         phone,
        "created_at":    datetime.utcnow(),
        "is_active":     True,
    }
    result = await db.users.insert_one(doc)
    doc["_id"] = result.inserted_id
    converted = _id(doc)
    await db.users.update_one(
        {"_id": result.inserted_id},
        {"$set": {"user_id": converted["id"]}}
    )
    converted["user_id"] = converted["id"]
    return converted


async def user_get_by_email(email: str) -> Optional[dict]:
    db = get_db()
    doc = await db.users.find_one({"email": email})
    return _id(doc) if doc else None


async def user_get_by_id(user_id: str) -> Optional[dict]:
    db = get_db()
    doc = await db.users.find_one({"_id": ObjectId(user_id)})
    return _id(doc) if doc else None


# ══════════════════════════════════════════════════════════════════════════════
# STEP 2 — Conversations
# ══════════════════════════════════════════════════════════════════════════════
# The /chat endpoint writes one doc per message to `conversation_history`:
#   {user_id, role, message, timestamp}
# Consecutive user→assistant messages are paired into {question, answer} turns
# for the profile extractor.

def _pair_history(docs: List[dict]) -> List[dict]:
    """Pair consecutive user→assistant messages into question/answer turns."""
    turns: List[dict] = []
    pending_q: Optional[str] = None
    for d in docs:
        role = d.get("role")
        msg  = d.get("message", "")
        if role == "user":
            pending_q = msg
        elif role == "assistant" and pending_q is not None:
            turns.append({"question": pending_q, "answer": msg})
            pending_q = None
    return turns


async def chat_history_pairs(user_id: str, limit: int = 500) -> List[dict]:
    """Return the user's chat as question/answer turns (oldest first)."""
    db = get_db()
    cursor = db.conversation_history.find({"user_id": user_id}).sort("timestamp", 1)
    docs = [doc async for doc in cursor]
    turns = _pair_history(docs)
    return turns[-limit:] if limit else turns


async def chat_history_pairs_since(user_id: str, since: datetime) -> List[dict]:
    """Return question/answer turns whose messages arrived after `since`."""
    db = get_db()
    cursor = (
        db.conversation_history
        .find({"user_id": user_id, "timestamp": {"$gt": since}})
        .sort("timestamp", 1)
    )
    docs = [doc async for doc in cursor]
    return _pair_history(docs)


# ══════════════════════════════════════════════════════════════════════════════
# STEP 2b — Chat sessions (sidebar threads)
# ══════════════════════════════════════════════════════════════════════════════
# A session is purely a display grouping over `conversation_history` (each
# message doc gets a `session_id`). The farmer's PROFILE (crop/district/land/
# last_task in `farmer_profiles`) is NOT session-scoped — it's the farmer's
# ongoing relationship with the bot, so starting a new session clears the
# visible thread but the advisory logic still remembers who they are.

async def session_create(user_id: str, title: str = "New chat") -> dict:
    db = get_db()
    now = datetime.utcnow()
    doc = {"user_id": user_id, "title": title, "created_at": now, "updated_at": now}
    result = await db.chat_sessions.insert_one(doc)
    doc["_id"] = result.inserted_id
    return _id(doc)


async def session_list(user_id: str, limit: int = 100) -> List[dict]:
    db = get_db()
    cursor = db.chat_sessions.find({"user_id": user_id}).sort("updated_at", -1).limit(limit)
    return [_id(doc) async for doc in cursor]


async def session_get(user_id: str, session_id: str) -> Optional[dict]:
    db = get_db()
    if not ObjectId.is_valid(session_id):
        return None
    doc = await db.chat_sessions.find_one({"_id": ObjectId(session_id), "user_id": user_id})
    return _id(doc) if doc else None


async def session_latest(user_id: str) -> Optional[dict]:
    db = get_db()
    doc = await db.chat_sessions.find_one({"user_id": user_id}, sort=[("updated_at", -1)])
    return _id(doc) if doc else None


async def session_touch(session_id: str, title: Optional[str] = None) -> None:
    db = get_db()
    update = {"updated_at": datetime.utcnow()}
    if title:
        update["title"] = title
    await db.chat_sessions.update_one({"_id": ObjectId(session_id)}, {"$set": update})


async def session_messages(user_id: str, session_id: str) -> List[dict]:
    db = get_db()
    cursor = (
        db.conversation_history
        .find({"user_id": user_id, "session_id": session_id})
        .sort("timestamp", 1)
    )
    return [
        {"role": d["role"], "message": d["message"], "timestamp": d["timestamp"]}
        async for d in cursor
    ]


async def session_delete(user_id: str, session_id: str) -> bool:
    db = get_db()
    if not ObjectId.is_valid(session_id):
        return False
    res = await db.chat_sessions.delete_one({"_id": ObjectId(session_id), "user_id": user_id})
    await db.conversation_history.delete_many({"user_id": user_id, "session_id": session_id})
    return res.deleted_count > 0


# ══════════════════════════════════════════════════════════════════════════════
# STEP 3 — Stage tracking
# ══════════════════════════════════════════════════════════════════════════════

async def stage_get(user_id: str) -> StageProgress:
    db = get_db()
    doc = await db.farmer_profiles.find_one(
        {"user_id": user_id}, {"stage_progress": 1}
    )
    if doc and "stage_progress" in doc:
        return StageProgress(**doc["stage_progress"])
    return StageProgress()


async def stage_advance(user_id: str, completed_stage: StageEnum, next_stage: StageEnum) -> StageProgress:
    db = get_db()
    now = datetime.utcnow()
    await db.farmer_profiles.update_one(
        {"user_id": user_id},
        {
            "$set": {
                "stage_progress.current_stage":    next_stage,
                "stage_progress.stage_updated_at": now,
            },
            "$addToSet": {"stage_progress.stages_completed": completed_stage},
            "$setOnInsert": {"user_id": user_id},
        },
        upsert=True,
    )
    return StageProgress(
        current_stage=next_stage,
        stages_completed=[completed_stage],
        stage_updated_at=now,
    )


# ══════════════════════════════════════════════════════════════════════════════
# STEP 4 — Farmer profile
# ══════════════════════════════════════════════════════════════════════════════

async def profile_upsert(user_id: str, fields: dict) -> dict:
    db = get_db()
    fields["extracted_at"] = datetime.utcnow()
    result = await db.farmer_profiles.find_one_and_update(
        {"user_id": user_id},
        {"$set": fields, "$setOnInsert": {"user_id": user_id}},
        upsert=True,
        return_document=True,
    )
    return _id(result)


async def profile_get(user_id: str) -> Optional[dict]:
    db = get_db()
    doc = await db.farmer_profiles.find_one({"user_id": user_id})
    return _id(doc) if doc else None


# ══════════════════════════════════════════════════════════════════════════════
# STEP 4b — Yield & Price lookups (income estimation)
# ══════════════════════════════════════════════════════════════════════════════

async def yield_data_get(district: str) -> Optional[dict]:
    """
    yield_data collection — one document per district:
      { district, potato, cauliflower, tomato }
    Values are in Mt/ha (tonnes per hectare).

    Returns the document directly so income calculator can do:
      yield_record.get("potato") → 15.7
    """
    db = get_db()
    doc = await db.yield_data.find_one({"district": district.lower()})
    return doc if doc else None


async def price_data_get(crop: str, month_num: int) -> Optional[dict]:
    """
    price_data collection — look up price for a crop and month.

    Handles two possible field names for month:
      - month_num (integer 1-12)  ← what load_csv_data.py saves
      - month (integer or string) ← fallback

    Adds "avg" = price_per_kg so income calculator always calls doc.get("avg").
    Falls back to nearest available month if exact not found.
    """
    db = get_db()

    # Try both field names for month
    doc = await db.price_data.find_one({
        "crop": crop.lower(),
        "$or": [
            {"month_num": month_num},
            {"month": month_num},
        ]
    })

    if not doc:
        # Load all price docs for this crop and find nearest month
        cursor     = db.price_data.find({"crop": crop.lower()})
        all_months = [d async for d in cursor]
        if not all_months:
            print(f"  ❌ No price_data at all for crop: {crop}")
            return None

        def _month_num(d):
            return d.get("month_num") or (d.get("month") if isinstance(d.get("month"), int) else 0)

        doc = min(all_months, key=lambda d: abs(_month_num(d) - month_num))
        print(f"  ⚠️  No exact price for {crop} month {month_num}, using month {_month_num(doc)}")

    # Normalize — income calculator always calls doc.get("avg")
    if "avg" not in doc:
        doc["avg"] = (
            doc.get("price_per_kg")
            or doc.get("price")
            or doc.get("avg_price")
        )

    if doc["avg"] is None:
        print(f"  ❌ price_data doc has no price field. Keys: {list(doc.keys())}")
        return None

    return doc


# ══════════════════════════════════════════════════════════════════════════════
# STEP 5 — Credit scoring
# ══════════════════════════════════════════════════════════════════════════════

async def credit_save(
    user_id: str,
    score: int,
    risk_level: str,
    breakdown: dict,
    explanation: str,
) -> dict:
    db = get_db()
    update = {
        "credit_score":      score,
        "risk_level":        risk_level,
        "score_breakdown":   breakdown,
        "score_explanation": explanation,
        "scored_at":         datetime.utcnow(),
    }
    result = await db.farmer_profiles.find_one_and_update(
        {"user_id": user_id},
        {"$set": update, "$setOnInsert": {"user_id": user_id}},
        upsert=True,
        return_document=True,
    )
    return _id(result)

async def admin_get_all_profiles(skip: int = 0, limit: int = 200) -> List[dict]:
    db = get_db()
    pipeline = [
        {"$sort":  {"credit_score": -1}},
        {"$skip":  skip},
        {"$limit": limit},
        {"$addFields": {"id": {"$toString": "$_id"}}},
        {"$project": {"_id": 0}},
    ]
    profiles = [doc async for doc in db.farmer_profiles.aggregate(pipeline)]

    enriched = []
    for p in profiles:
        # Always append — even if user lookup fails
        try:
            user = await user_get_by_id(p["user_id"])
            if user:
                p["name"]  = user.get("name")
                p["email"] = user.get("email")
                p["phone"] = user.get("phone")
        except Exception:
            pass

        # Your DB stores "location" but frontend expects "district"
        if not p.get("district") and p.get("location"):
            p["district"] = p["location"]

        # Your DB stores "experience_year" (singular) not "experience_years"
        if not p.get("experience_years") and p.get("experience_year") is not None:
            p["experience_years"] = p["experience_year"]

        enriched.append(p)

    return enriched


async def admin_profile_count() -> int:
    db = get_db()
    return await db.farmer_profiles.count_documents({})



