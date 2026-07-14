from pymongo import MongoClient
import os
from dotenv import load_dotenv

load_dotenv()
uri = os.getenv("MONGODB_URI")
db_name = os.getenv("MONGODB_DB_NAME")

client = MongoClient(uri)
db = client[db_name]

# Ensure we have the user
db.farmer_profiles.delete_many({"phone_number": "9812345678", "farmer_type": "B"})

db.farmer_profiles.insert_one({
    "phone_number": "9812345678",
    "name": "Dummy Type B Farmer",
    "district": "Kathmandu",
    "zone": "Hills",
    "farmer_type": "B",
    "is_active": True,
    "telegram_chat_id": str(os.getenv("telegram_chat_id")),
    "preferred_language": "nepali",
    "type_b_detail": {
        "season": "Spring"
    }
})
print("Dummy Type B farmer created.")
client.close()
