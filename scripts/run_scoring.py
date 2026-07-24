import asyncio
from db.mongo import connect_db
from core.credit_scorer import score_all_farmers

async def main():
    # STEP 1: connect DB FIRST
    await connect_db()

    # STEP 2: run scoring
    result = await score_all_farmers()
    print(result)

if __name__ == "__main__":
    asyncio.run(main())