from __future__ import annotations
import logging
import asyncio
import json
from datetime import datetime, date
from typing import Optional


import httpx
from apscheduler.schedulers.background import BackgroundScheduler
from apscheduler.triggers.cron import CronTrigger
from pymongo import MongoClient
import certifi

from config import get_settings
from graph import state
from graph.workflow import get_advisory_graph
from rules.das_gdd import calculate_das, get_growth_stage, get_zone_temperature_defaults
from rules.nepali_date_converter import nepali_to_english_date

settings = get_settings()

# ── Delivery channel from config
DELIVERY_CHANNEL: str = getattr(settings, "delivery_channel", "simulate")
TELEGRAM_BOT_TOKEN: str = getattr(settings, "telegram_bot_token", "")
WHATSAPP_TOKEN: str = getattr(settings, "whatsapp_token", "")
WHATSAPP_PHONE_ID: str = getattr(settings, "whatsapp_phone_number_id", "")
SCHEDULER_HOUR: int = int(getattr(settings, "scheduler_hour", 8))
SCHEDULER_MINUTE: int = int(getattr(settings, "scheduler_minute", 0))
TIMEZONE: str = getattr(settings, "timezone", "Asia/Kathmandu")

logger = logging.getLogger(__name__)


# ─────────────────────────────────────────────
# Helpers
# ─────────────────────────────────────────────

def _parse_sowing_date(raw) -> Optional[date]:
    """Parse a sowing date from string / datetime / date → date, or None."""
    if isinstance(raw, str):
        ad_date_str = nepali_to_english_date(raw)
        try:
            return date.fromisoformat(ad_date_str) if ad_date_str else None
        except (ValueError, TypeError):
            return None
    if isinstance(raw, datetime):
        return raw.date()
    if isinstance(raw, date):
        return raw
    return None


def _should_notify(crop: str, sowing_date: date, zone: str) -> bool:
    """
    Rule: Notify if today is within the first 2 days of a new growth stage,
    has fertilizer actions, or the stage has a critical alert.
    Max notifications: 1-3 per week.
    """
    from rules.das_gdd import CROP_STAGES, _DEFAULT_STAGES, estimate_gdd

    das = calculate_das(sowing_date)
    temps = get_zone_temperature_defaults(zone)
    gdd = estimate_gdd(
        sowing_date=sowing_date,
        avg_tmax=temps["avg_tmax"],
        avg_tmin=temps["avg_tmin"],
        base_temp=settings.base_temp_celsius,
    )
    crop_title = crop.strip().title()
    stages = CROP_STAGES.get(crop_title, _DEFAULT_STAGES)

    for stage in stages:
        if stage.das_start <= das < stage.das_end:
            days_into_stage = das - stage.das_start

            # Notify on stage entry
            if days_into_stage <= 2:
                return True

            # Notify if fertilizer action is due
            fertilizer_keywords = [
                "urea", "dap", "mop", "fertilizer",
                "nitrogen", "phosphorus", "potassium",
            ]
            has_fert_action = any(
                kw in act.lower()
                for act in stage.key_activities
                for kw in fertilizer_keywords
            )
            if has_fert_action and days_into_stage <= 5:
                return True

            # Always notify for critical stages
            critical_stage = [
                "flowering", "panicle", "tillering",
                "tuber initiation", "blight",
            ]
            if any(cs in stage.name.lower() for cs in critical_stage):
                return True

            return False

    return False


# ─────────────────────────────────────────────
# State builder
# ─────────────────────────────────────────────

from rules.weather_integration import fetch_7_day_forecast


def _build_state_from_profile(profile: dict) -> dict:
    """Convert a MongoDB farmer profile doc to a KrishiMitraState dict."""
    farmer_type = profile.get("farmer_type", "A").upper()
    zone = profile.get("zone", "Hills")

    weather_data = fetch_7_day_forecast(zone)

    type_a = profile.get("type_a_detail") or {}
    type_b = profile.get("type_b_detail") or {}

    sowing_raw = type_a.get("sowing_date") or profile.get("sowing_date")
    sowing_date = _parse_sowing_date(sowing_raw)

    return {
        "profile_id":        str(profile["_id"]),
        "farmer_type":       farmer_type,
        "district":          profile.get("district", ""),
        "soil_type":         profile.get("soil_type"),
        "land_area_ha":      profile.get("land_area_ha"),
        "language":          profile.get("language", "nepali"),
        "safety_flags":      [],
        "has_critical_flags": False,
        "weather_data":      weather_data,
        # Type A fields
        "crop":              type_a.get("crop") or profile.get("crop", ""),
        "variety":           type_a.get("variety") or profile.get("variety"),
        "sowing_date":       sowing_date,
        "observed_issues":   type_a.get("observed_issues") or profile.get("observed_issues"),
        "last_fertilizer":   type_a.get("last_fertilizer") or profile.get("last_fertilizer"),
        "last_pesticide":    type_a.get("last_pesticide") or profile.get("last_pesticide"),
        # Type B fields
        "season":            type_b.get("season") or profile.get("season"),
        "irrigation_access": type_b.get("irrigation_access") or profile.get("irrigation_access", "Rainfed"),
        "market_preference": type_b.get("market_preference") or profile.get("market_preference"),
        "budget_npr":        type_b.get("budget_npr") or profile.get("budget_npr"),
    }


# ─────────────────────────────────────────────
# Deduplication
# ─────────────────────────────────────────────

def _already_notified_today(
    db, profile_id: str, crop: str, stage_name: str, is_type_b: bool = False
) -> bool:
    today_start = datetime.utcnow().replace(hour=0, minute=0, second=0, microsecond=0)
    query = {
        "profile_id":     profile_id,
        "created_at":     {"$gte": today_start},
        "delivery_status": "sent",
    }
    if not is_type_b:
        query["crop"]         = crop
        query["growth_stage"] = stage_name

    return db["notifications"].find_one(query) is not None


# ─────────────────────────────────────────────
# Delivery layer
# ─────────────────────────────────────────────

def _choose_message(record: dict, language: str) -> str:
    return record.get("message_ne") if language == "nepali" else record.get("message_en", "")


def _deliver_simulate(record: dict) -> dict:
    """Demo mode: log and save to MongoDB only."""
    logger.info(
        "[SIMULATE] → %s | %s DAS %s | %s",
        record["farmer_name"],
        record.get("crop", "N/A"),
        record.get("days_after_sowing", "N/A"),
        record.get("message_en", "")[:60],
    )
    return {**record, "delivery_status": "sent", "sent_at": datetime.utcnow()}


def _deliver_telegram(record: dict) -> dict:
    """
    Telegram Bot delivery.

    Setup (2 min):
      1. Message @BotFather → /newbot → get TELEGRAM_BOT_TOKEN
      2. Farmer messages your bot → get their chat_id from the update
      3. Store chat_id in farmer profile as telegram_chat_id
      4. Set DELIVERY_CHANNEL=telegram in .env
    """
    token   = TELEGRAM_BOT_TOKEN
    chat_id = record.get("telegram_chat_id")

    if not token or not chat_id:
        logger.warning(
            "[TELEGRAM] No token or chat_id for %s — falling back to simulate",
            record["farmer_name"],
        )
        return _deliver_simulate(record)

    message = _choose_message(record, record.get("language", "nepali"))
    url = f"https://api.telegram.org/bot{token}/sendMessage"

    try:
        resp = httpx.post(url, json={"chat_id": chat_id, "text": message}, timeout=10)
        resp.raise_for_status()
        logger.info("[TELEGRAM] Sent to %s", record["farmer_name"])
        return {**record, "delivery_status": "sent", "sent_at": datetime.utcnow()}
    except Exception as e:
        logger.error("[TELEGRAM] Failed for %s: %s", record["farmer_name"], e)
        return {**record, "delivery_status": "failed", "delivery_error": str(e)}


def _deliver_whatsapp(record: dict) -> dict:
    """
    Meta WhatsApp Business Cloud API delivery.
    Production use only — requires Meta Business approval.
    """
    if not WHATSAPP_TOKEN or not WHATSAPP_PHONE_ID:
        logger.warning("[WHATSAPP] Credentials not set — falling back to simulate")
        return _deliver_simulate(record)

    phone   = record.get("phone", "").replace("+", "").replace("-", "").replace(" ", "")
    message = _choose_message(record, record.get("language", "nepali"))

    url     = f"https://graph.facebook.com/v19.0/{WHATSAPP_PHONE_ID}/messages"
    headers = {"Authorization": f"Bearer {WHATSAPP_TOKEN}", "Content-Type": "application/json"}
    payload = {
        "messaging_product": "whatsapp",
        "to":   phone,
        "type": "text",
        "text": {"body": message},
    }

    try:
        resp = httpx.post(url, json=payload, headers=headers, timeout=15)
        resp.raise_for_status()
        logger.info("[WHATSAPP] Sent to %s", record["farmer_name"])
        return {**record, "delivery_status": "sent", "sent_at": datetime.utcnow()}
    except Exception as e:
        logger.error("[WHATSAPP] Failed for %s: %s", record["farmer_name"], e)
        return {**record, "delivery_status": "failed", "delivery_error": str(e)}


def _deliver(record: dict) -> dict:
    channel = DELIVERY_CHANNEL
    if channel == "telegram":
        return _deliver_telegram(record)
    elif channel == "whatsapp":
        return _deliver_whatsapp(record)
    return _deliver_simulate(record)


# ─────────────────────────────────────────────
# Notification record builders
# ─────────────────────────────────────────────

def _build_notification_record(profile: dict, final_state: dict) -> dict:
    """
    Build the MongoDB notification document from the LangGraph final state.
    Used for Type A (crop-advisory) farmers only.
    """
    growth_stage = final_state.get("growth_stage")
    stage_name   = growth_stage.name if growth_stage else "Unknown"
    das          = final_state.get("das", 0)
    crop         = final_state.get("crop", "")

    final_msg = final_state.get("final_message", "")
    language  = final_state.get("language", "nepali")

    if language == "nepali":
        message_ne = final_msg
        message_en = _template_message_en(profile, final_state, stage_name, das, crop)
    else:
        message_en = final_msg
        message_ne = _template_message_ne(profile, final_state, stage_name, das, crop)

    return {
        "profile_id":        str(profile["_id"]),
        "farmer_name":       profile.get("name", ""),
        "phone":             profile.get("phone_number", ""),
        "language":          language,
        "telegram_chat_id":  profile.get("telegram_chat_id"),
        "crop":              crop,
        "days_after_sowing": das,
        "growth_stage":      stage_name,
        "message_en":        message_en,
        "message_ne":        message_ne,
        "rule_output":       json.dumps(final_state.get("rule_output", {}), ensure_ascii=False),
        "has_critical_flags": final_state.get("has_critical_flags", False),
        "safety_flags":      [
            {"severity": f.severity, "message": f.message}
            for f in final_state.get("safety_flags", [])
        ],
        "farmer_type":      "A",
        "delivery_channel": DELIVERY_CHANNEL,
        "delivery_status":  "pending",
        "triggered_by":     "scheduler",
        "created_at":       datetime.utcnow(),
    }


def _build_type_b_notification_record(profile: dict, message_en: str, message_ne: str) -> dict:
    """
    Build the MongoDB notification document for Type B (planning) farmers.
    Does NOT depend on crop/DAS/growth-stage fields.
    """
    language = profile.get("language", "nepali")
    return {
        "profile_id":        str(profile["_id"]),
        "farmer_name":       profile.get("name", ""),
        "phone":             profile.get("phone_number", ""),
        "language":          language,
        "telegram_chat_id":  profile.get("telegram_chat_id"),
        # Type B has no crop / DAS / growth stage
        "crop":              None,
        "days_after_sowing": None,
        "growth_stage":      None,
        "message_en":        message_en,
        "message_ne":        message_ne,
        "rule_output":       "{}",
        "has_critical_flags": False,
        "safety_flags":      [],
        "farmer_type":       "B",
        "delivery_channel":  DELIVERY_CHANNEL,
        "delivery_status":   "pending",
        "triggered_by":      "scheduler",
        "created_at":        datetime.utcnow(),
    }


def _template_message_en(profile: dict, state: dict, stage: str, das: int, crop: str) -> str:
    """Quick English template — used when primary language is Nepali (Type A)."""
    name       = profile.get("name", "Farmer")
    activities = []
    gs = state.get("growth_stage")
    if gs:
        activities = gs.key_activities[:2]

    lines = [
        f"🌾 KrishiMitra Update — {name}",
        f"Your {crop} is at Day {das} ({stage} stage).",
    ]
    if activities:
        lines.append(f"Action: {activities[0]}")
    flags    = state.get("safety_flags", [])
    critical = [f for f in flags if f.severity == "CRITICAL"]
    if critical:
        lines.append(f"⚠️ ALERT: {critical[0].message}")
    return "\n".join(lines)


def _template_message_ne(profile: dict, state: dict, stage: str, das: int, crop: str) -> str:
    """Quick Nepali template — used when primary language is English (Type A)."""
    name     = profile.get("name", "किसान")
    gs       = state.get("growth_stage")
    stage_ne = gs.name if gs else stage

    lines = [
        f"🌾 कृषिमित्र अपडेट — {name}",
        f"तपाईंको {crop} अहिले {das} दिनमा छ ({stage_ne} अवस्था)।",
    ]
    if gs and gs.key_activities:
        lines.append(f"आज गर्नुहोस्: {gs.key_activities[0]}")
    flags    = state.get("safety_flags", [])
    critical = [f for f in flags if f.severity == "CRITICAL"]
    if critical:
        lines.append(f"⚠️ सावधान: {critical[0].message}")
    return "\n".join(lines)


# ─────────────────────────────────────────────
# Main notification job
# ─────────────────────────────────────────────

async def run_notification_job() -> dict:
    """
    Main scheduler job.
    Fetches all active Type A and Type B farmers and runs the correct
    pipeline for each type independently.
    Returns summary: {sent, skipped, errors}
    """
    started_at = datetime.utcnow()
    logger.info("=" * 60)
    logger.info("KrishiMitra Notification Job started: %s", started_at.strftime("%Y-%m-%d %H:%M"))
    logger.info("=" * 60)

    client = MongoClient(settings.mongodb_uri, tlsCAFile=certifi.where())
    db = client[settings.mongodb_db_name]

    sent = skipped = errors = 0

    try:
        profiles = list(db["farmer_profiles"].find({
            "farmer_type": {"$in": ["A", "B"]},
            "is_active":   True,
        }))
        logger.info("Found %d active farmers", len(profiles))

        for profile in profiles:
            farmer_name = profile.get("name", "Unknown")
            profile_id  = str(profile["_id"])
            farmer_type = profile.get("farmer_type", "A").upper()

            try:
                # ── TYPE A: Crop-advisory pipeline ──────────────────────────
                if farmer_type == "A":
                    type_a = profile.get("type_a_detail") or {}
                    crop   = type_a.get("crop") or profile.get("crop", "")
                    zone   = profile.get("zone", "Hills")

                    sowing_raw  = type_a.get("sowing_date") or profile.get("sowing_date")
                    sowing_date = _parse_sowing_date(sowing_raw)

                    if not sowing_date:
                        logger.warning("  [SKIP] %s — no valid sowing_date", farmer_name)
                        skipped += 1
                        continue

                    if not crop:
                        logger.warning("  [SKIP] %s — no crop in profile", farmer_name)
                        skipped += 1
                        continue

                    if not _should_notify(crop, sowing_date, zone):
                        logger.info(
                            "  [SKIP] %s — no notification needed today (DAS=%d)",
                            farmer_name, calculate_das(sowing_date),
                        )
                        skipped += 1
                        continue

                    das         = calculate_das(sowing_date)
                    quick_stage = get_growth_stage(crop, das)
                    stage_name  = quick_stage.name if quick_stage else "Unknown"

                    if _already_notified_today(db, profile_id, crop, stage_name):
                        logger.info(
                            "  [SKIP] %s — already notified today (stage=%s)",
                            farmer_name, stage_name,
                        )
                        skipped += 1
                        continue

                    logger.info(
                        "  [RUN] Type A %s | %s DAS=%d stage=%s",
                        farmer_name, crop, das, stage_name,
                    )

                    initial_state = _build_state_from_profile(profile)
                    final_state   = await get_advisory_graph().ainvoke(initial_state)

                    if final_state.get("error"):
                        logger.error(
                            "  [ERROR] Graph error for %s: %s",
                            farmer_name, final_state["error"],
                        )
                        errors += 1
                        continue

                    record = _build_notification_record(profile, final_state)

                # ── TYPE B: Planning/seasonal advisory pipeline ──────────────
                elif farmer_type == "B":
                    if _already_notified_today(db, profile_id, crop="", stage_name="", is_type_b=True):
                        logger.info("  [SKIP] %s — already notified today (Type B)", farmer_name)
                        skipped += 1
                        continue

                    logger.info("  [RUN] Type B %s", farmer_name)

                    trigger = check_planning_farmer_triggers(profile)
                    if not trigger.get("send"):
                        logger.info("  [SKIP] %s — Type B trigger returned send=False", farmer_name)
                        skipped += 1
                        continue

                    # Build bilingual messages from the trigger result
                    message_en = trigger.get("message", "")
                    message_ne = trigger.get("message_ne", "") or _build_type_b_message_ne(profile, trigger)

                    record = _build_type_b_notification_record(profile, message_en, message_ne)

                else:
                    logger.warning("  [SKIP] %s — unknown farmer_type=%s", farmer_name, farmer_type)
                    skipped += 1
                    continue

                # ── Common delivery + persistence ────────────────────────────
                delivered = _deliver(record)
                db["notifications"].insert_one(delivered)

                if delivered["delivery_status"] == "sent":
                    logger.info(
                        "  [SENT] %s | %s",
                        farmer_name,
                        delivered.get("message_en", "")[:50],
                    )
                    sent += 1
                else:
                    logger.warning(
                        "  [FAILED] %s — %s",
                        farmer_name, delivered.get("delivery_error"),
                    )
                    errors += 1

            except Exception as e:
                logger.exception("  [ERROR] Exception processing %s: %s", farmer_name, e)
                errors += 1

    finally:
        client.close()

    duration = (datetime.utcnow() - started_at).total_seconds()
    logger.info(
        "Job done in %.1fs — sent=%d skipped=%d errors=%d",
        duration, sent, skipped, errors,
    )
    return {"sent": sent, "skipped": skipped, "errors": errors}


# ─────────────────────────────────────────────
# Type B helpers
# ─────────────────────────────────────────────

def _build_type_b_message_ne(profile: dict, trigger: dict) -> str:
    """Generate a Nepali version of the Type B planning message."""
    name   = profile.get("name", "किसान")
    type_b = profile.get("type_b_detail") or {}
    zone   = profile.get("zone", "")
    season = type_b.get("season") or profile.get("season", "")
    return (
        f"🌾 कृषिमित्र अपडेट — {name}\n"
        f"मनसुन तयारीको समय आयो। तपाईंको {zone} क्षेत्रको {season} सिजनको लागि "
        f"कृषिमित्रमा उपयुक्त बाली हेर्नुहोस्।"
    )


# ─────────────────────────────────────────────
# Sync wrapper for APScheduler
# ─────────────────────────────────────────────

def _run_job_sync():
    asyncio.run(run_notification_job())


# ─────────────────────────────────────────────
# APScheduler setup
# ─────────────────────────────────────────────

_scheduler = BackgroundScheduler(timezone=TIMEZONE)


def start_schedular():
    """
    Start the background scheduler.
    Call this from main.py lifespan startup.
    """
    if _scheduler.running:
        logger.warning("Scheduler already running — skip start")
        return

    _scheduler.add_job(
        _run_job_sync,
        trigger=CronTrigger(hour=SCHEDULER_HOUR, minute=SCHEDULER_MINUTE, timezone=TIMEZONE),
        id="daily_notification",
        name="Daily KrishiMitra Notification Job",
        replace_existing=True,
        misfire_grace_time=3600,
    )
    _scheduler.start()
    logger.info(
        "Scheduler started with daily job at %02d:%02d %s",
        SCHEDULER_HOUR, SCHEDULER_MINUTE, TIMEZONE,
    )


def stop_scheduler():
    """Call from main.py lifespan shutdown."""
    if _scheduler.running:
        _scheduler.shutdown(wait=False)
        logger.info("Scheduler stopped")


# ─────────────────────────────────────────────
# Legacy / backwards-compatible functions
# ─────────────────────────────────────────────

def evaluate_farmer_notification(farmer_profile: dict, weather_data=None) -> dict:
    """
    Evaluates whether a farmer needs a notification.
    Legacy function — delegates to the correct pipeline per farmer type.
    Kept so existing callers don't break.
    """
    farmer_type = farmer_profile.get("farmer_type", "A").upper()
    if farmer_type == "A":
        return check_active_farmer_triggers(farmer_profile, weather_data)
    return check_planning_farmer_triggers(farmer_profile)


def check_active_farmer_triggers(profile: dict, weather_data=None) -> dict:
    """
    Check if a Type A (active crop) farmer needs a notification.
    Uses the real rule engine.
    """
    type_a = profile.get("type_a_detail") or {}
    crop   = type_a.get("crop") or profile.get("crop", "")
    zone   = profile.get("zone", "Hills")

    sowing_raw  = type_a.get("sowing_date") or profile.get("sowing_date")
    sowing_date = _parse_sowing_date(sowing_raw)

    if not sowing_date or not crop:
        return {"send": False, "message": ""}

    if not _should_notify(crop, sowing_date, zone):
        return {"send": False, "message": ""}

    das        = calculate_das(sowing_date)
    stage      = get_growth_stage(crop, das)
    activities = stage.key_activities[:2] if stage else []
    activity_str = activities[0] if activities else "Monitor your crop today."

    return {
        "send": True,
        "message": (
            f"Your {crop} is at Day {das} ({stage.name if stage else 'current stage'}). "
            f"{activity_str}"
        ),
    }


def check_planning_farmer_triggers(profile: dict) -> dict:
    """
    Check if a Type B (planning) farmer needs a seasonal reminder.
    Returns send=True with bilingual messages.
    Phase 2: integrate ML crop recommendation model here.
    """
    zone   = profile.get("zone", "")
    type_b = profile.get("type_b_detail") or {}
    season = type_b.get("season") or profile.get("season", "")
    name   = profile.get("name", "Farmer")

    message_en = (
        f"🌾 KrishiMitra Update — {name}\n"
        f"Monsoon preparation time. For your {zone} land this {season} season, "
        f"review crop options on KrishiMitra."
    )
    message_ne = (
        f"🌾 कृषिमित्र अपडेट — {name}\n"
        f"मनसुन तयारीको समय आयो। तपाईंको {zone} क्षेत्रको {season} सिजनको लागि "
        f"कृषिमित्रमा उपयुक्त बाली हेर्नुहोस्।"
    )

    return {
        "send":       True,
        "message":    message_en,
        "message_en": message_en,
        "message_ne": message_ne,
    }