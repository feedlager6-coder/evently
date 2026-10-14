import asyncio
import sys
from pathlib import Path
import pprint

backend_dir = Path(__file__).resolve().parent.parent.parent
sys.path.insert(0, str(backend_dir))

from app.database import AsyncSessionLocal
from app.models.event import Event
from app.services.telegram_bot import build_event_inline_result, handle_inline_query
from sqlalchemy import select


async def main():
    async with AsyncSessionLocal() as session:
        ev = (await session.execute(select(Event).where(Event.id == "31af282b-65b9-4ec3-8f05-86d3e32ff513"))).scalar_one()
        print("=== EVENT DETAILS ===")
        print(f"Title: {ev.title}")
        print(f"Cover URL: {ev.cover_image_url}")

        print("\n=== BUILD_EVENT_INLINE_RESULT (is_share=False) ===")
        inline_art = build_event_inline_result(ev, is_share=False)
        pprint.pprint(inline_art)

        print("\n=== BUILD_EVENT_INLINE_RESULT (is_share=True) ===")
        inline_photo = build_event_inline_result(ev, is_share=True)
        pprint.pprint(inline_photo)

        print("\n=== HANDLE_INLINE_QUERY (query='Махачкала') ===")
        res = await handle_inline_query(session, {"id": "q1", "query": "Махачкала", "from": {"id": 847668803}})
        for item in res.get("results", []):
            if "Вечеринка" in item.get("title", ""):
                print("Found in inline search results:")
                pprint.pprint(item)


if __name__ == "__main__":
    asyncio.run(main())
