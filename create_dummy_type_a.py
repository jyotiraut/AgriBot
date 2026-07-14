from pymongo import MongoClient
import os
from datetime import datetime, timedelta
from dotenv import load_dotenv

load_dotenv()
uri = os.getenv("MONGODB_URI")
db_name = os.getenv("MONGODB_DB_NAME")

client = MongoClient(uri)
db = client[db_name]

# Ensure we have the user
db.farmer_profiles.delete_many({"phone_number": "9812345679", "farmer_type": "A"})

# Calculate sowing date (10 days ago)
sowing_date = (datetime.now() - timedelta(days=10)).strftime("%Y-%m-%d")

db.farmer_profiles.insert_one({
    "phone_number": "9812345679",
    "name": "Dummy Type A Farmer",
    "district": "Kathmandu",
    "zone": "Hills",
    "farmer_type": "A",
    "is_active": True,
    "telegram_chat_id": str(os.getenv("telegram_chat_id")),
    "preferred_language": "nepali",
    "type_a_detail": {
        "crop": "Tomato",
        "variety": "Sabitri",
        "sowing_date": sowing_date,
        "observed_issues": None,
        "last_fertilizer_applied": {
            "name": "Urea",
            "kg_per_ha": 50,
            "applied_date": sowing_date
        },
        "last_pesticide_applied": {
            "name": "Mancozeb",
            "ml_per_ha": 100,
            "applied_date": sowing_date
        }
    }
})
print(f"Dummy Type A farmer created with sowing date: {sowing_date}")
client.close()
