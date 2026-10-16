import asyncio
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent.parent))

from sqlalchemy import text
from app.database import AsyncSessionLocal


async def run_checks():
    async with AsyncSessionLocal() as session:
        print("=== QUERY 1: Попурри events ===")
        res1 = await session.execute(
            text("SELECT title, category_id, venue_name FROM events WHERE title ILIKE '%Попурри%';")
        )
        rows1 = res1.all()
        for r in rows1:
            print(f"TITLE: {r[0]} | CATEGORY: {r[1]} | VENUE: {r[2]}")
        if not rows1:
            print("No events found with title ILIKE '%Попурри%'")

        print("\n=== QUERY 2: Top 25 Exhibitions ===")
        res2 = await session.execute(
            text("SELECT title, venue_name FROM events WHERE category_id = 'exhibitions' LIMIT 25;")
        )
        rows2 = res2.all()
        for i, r in enumerate(rows2, 1):
            print(f"{i}. {r[0]} | VENUE: {r[1]}")
        print(f"Total shown: {len(rows2)}")


if __name__ == "__main__":
    asyncio.run(run_checks())
