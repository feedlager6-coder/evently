import asyncio
import sys
from pathlib import Path

sys.path.insert(0, "/app")
sys.path.insert(0, "/app/backend")

from backend.app.database import AsyncSessionLocal
from backend.app.services.telegram_bot import handle_inline_query

async def main():
    async with AsyncSessionLocal() as session:
        res = await handle_inline_query(session, {"id": "test1", "query": "Махачкала"})
        results = res.get("results", [])
        print(f"\n=== INLINE QUERY VERIFICATION (Total: {len(results)}) ===")
        for i, r in enumerate(results[:5]):
            print(f"[{i+1}] Title: {r.get('title')}")
            print(f"    Thumb: {r.get('thumbnail_url')}")
            photo = r.get("input_message_content", {}).get("link_preview_options", {}).get("url")
            print(f"    Photo: {photo}")

if __name__ == "__main__":
    asyncio.run(main())
