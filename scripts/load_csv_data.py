"""
scripts/load_csv_data.py
"""

import asyncio
import argparse
import csv
import os
import sys
from pathlib import Path
from dotenv import load_dotenv
from motor.motor_asyncio import AsyncIOMotorClient

load_dotenv()

sys.path.insert(0, str(Path(__file__).parent.parent))

_client = None
_db = None


async def connect_csv_db():
    global _client, _db

    mongo_uri = os.getenv("MONGO_URI") or os.getenv("MONGODB_URI") or "mongodb+srv://pal98112016_db_user:Sarqici5Rp4g6lpc@cluster0.bncjzty.mongodb.net/?appName=Cluster0"

    mongo_db = os.getenv("MONGO_DB_NAME") or os.getenv("MONGODB_DB_NAME") or "krishimitra"

    _client = AsyncIOMotorClient(
        mongo_uri,
        serverSelectionTimeoutMS=5000
    )

    _db = _client[mongo_db]

    await _client.admin.command("ping")
    print("✅ Connected to MongoDB")


def get_db():
    return _db

YIELD_COLUMN_MAP = {
    "Potato_Yield_Mt_per_Ha":      "potato",
    "Cauliflower_Yield_Mt_per_ha": "cauliflower",
    "Tomato_Yield_Mt_per_ha":      "tomato",
}


async def load_yield_data(filepath: str) -> int:
    docs = []

    with open(filepath, newline="", encoding="utf-8-sig") as f:
        reader = csv.DictReader(f, delimiter=",")

        for row in reader:
            district = row.get("District", "").strip()
            if not district:
                continue

            doc = {"district": district.lower()}

            for csv_col, field_name in YIELD_COLUMN_MAP.items():
                raw = row.get(csv_col, "").strip()
                try:
                    doc[field_name] = float(raw) if raw else None
                except ValueError:
                    doc[field_name] = None

            docs.append(doc)

    if not docs:
        print("❌ No yield data parsed — check column names")
        return 0

    db = get_db()
    await db.yield_data.drop()
    await db.yield_data.insert_many(docs)
    await db.yield_data.create_index("district")

    print(f"✅ yield_data loaded — {len(docs)} districts")

    print("\n── Sample yield_data ──")
    async for doc in db.yield_data.find({}, {"_id": 0}).limit(3):
        print(" ", doc)

    return len(docs)


async def load_price_data(filepath: str) -> int:
    docs = []

    commodity_map = {
        "potato":      "potato",
        "tomato":      "tomato",
        "cauliflower": "cauliflower",
        "cauli":       "cauliflower",
    }

    with open(filepath, newline="", encoding="utf-8-sig") as f:
        sample = f.read(2048)
        f.seek(0)
        delimiter = "\t" if sample.count("\t") > sample.count(",") else ","

        header_line = f.readline().strip()
        print(f"   CSV headers detected: {header_line}")
        f.seek(0)

        reader = csv.DictReader(f, delimiter=delimiter)

        for row in reader:
            commodity_raw = row.get("Commodity", "").strip().lower()

            crop = None
            for key, val in commodity_map.items():
                if key in commodity_raw:
                    crop = val
                    break

            if not crop:
                continue

            try:
                month      = int(row.get("BS_Month", 0) or 0)
                month_name = row.get("Month_Name", "").strip()
                avg_price  = float(row.get("Monthly_Avg", 0) or 0)
                min_price  = float(row.get("Monthly_Min", 0) or 0)
                max_price  = float(row.get("Monthly_Max", 0) or 0)
            except (ValueError, TypeError):
                continue

            if month == 0 or avg_price == 0:
                continue

            docs.append({
                "crop":       crop,
                "month":      month,
                "month_name": month_name,
                "min":        min_price,
                "max":        max_price,
                "avg":        avg_price,
            })

    if not docs:
        print("❌ No price data parsed — check column names")
        return 0

    db = get_db()
    await db.price_data.drop()
    await db.price_data.insert_many(docs)
    await db.price_data.create_index([("crop", 1), ("month", 1)])

    print(f"✅ price_data loaded — {len(docs)} rows")

    from collections import Counter
    counts = Counter(d["crop"] for d in docs)
    for crop, count in counts.items():
        print(f"   {crop}: {count} months")

    print("\n── Potato prices by BS month ──")
    async for doc in db.price_data.find(
        {"crop": "potato"}, {"_id": 0}
    ).sort("month", 1):
        print(f"  BS Month {doc['month']:2d} ({doc['month_name']})  avg={doc['avg']} NPR/kg")

    return len(docs)


async def main(yield_path: str, price_path: str):
    print("🔌 Connecting to MongoDB...")
    await connect_csv_db()

    print(f"\n📂 Loading yield data from: {yield_path}")
    y = await load_yield_data(yield_path)

    print(f"\n📂 Loading price data from: {price_path}")
    p = await load_price_data(price_path)

    print(f"\n✅ All done — {y} yield docs + {p} price docs in MongoDB")

    if _client:
        _client.close()


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--yield", dest="yield_path", required=True)
    parser.add_argument("--price", dest="price_path", required=True)
    args = parser.parse_args()

    for path in [args.yield_path, args.price_path]:
        if not Path(path).exists():
            print(f"❌ File not found: {path}")
            sys.exit(1)

    asyncio.run(main(args.yield_path, args.price_path))