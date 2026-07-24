# scripts/backfill_sowing_dates.py
"""
One-time migration script.
Finds all profiles where sowing_date is stored in Nepali (BS) format
and converts them to English (AD) ISO strings ("YYYY-MM-DD").

Run once:
    python -m scripts.backfill_sowing_dates

Safe to re-run — already-converted dates (matching YYYY-MM-DD with year < 2040)
are skipped automatically.
"""

import asyncio
import re

from db import crud
from rules.nepali_date_converter import nepali_to_english_date


def _already_ad(value: str) -> bool:
    """Return True if the value looks like an AD ISO date (year 2020-2039)."""
    return bool(re.fullmatch(r"20[012]\d-\d{2}-\d{2}", value.strip()))


async def main() -> None:
    profiles = await crud.profiles_get_all()   # add this method if not present — see note below

    converted = 0
    skipped   = 0
    errors    = 0

    for p in profiles:
        user_id = p.get("user_id") or str(p.get("_id", ""))
        raw     = p.get("sowing_date")

        if not raw:
            skipped += 1
            continue

        if _already_ad(raw):
            skipped += 1
            continue

        result = nepali_to_english_date(raw)

        if result == raw:
            # Converter returned the original — unparseable, leave it alone
            print(f"⚠️  Could not convert  | user: {user_id} | value: '{raw}'")
            errors += 1
            continue

        await crud.profile_upsert(user_id, {"sowing_date": result})
        print(f"✅ Converted  | user: {user_id} | '{raw}' → '{result}'")
        converted += 1

    print(
        f"\nDone — converted: {converted} | skipped: {skipped} | unparseable: {errors}"
    )


if __name__ == "__main__":
    asyncio.run(main())


# ── Note: crud.profiles_get_all() ────────────────────────────────────────────
# If this method doesn't exist yet, add it to db/crud.py:
#
#   async def profiles_get_all() -> list[dict]:
#       return await db["profiles"].find({}).to_list(length=None)