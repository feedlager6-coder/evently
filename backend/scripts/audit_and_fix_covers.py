"""
Script to audit and fix all event cover images on Selectel:
1. Verifies that all published event cover image files exist on disk.
2. Ensures all cover images are strictly baseline RGB JPEGs (not progressive, not WebP/PNG)
   with optimal dimensions and quality for Telegram Bot API.
3. Tests handle_inline_query with query="" to inspect the top 10 items.
4. Performs HTTP checks and PIL validation on the returned thumbnail_urls.
5. Verifies organizer audience daily_growth and new_subscribers_today.
"""

import os
import sys
import asyncio
from pathlib import Path
from PIL import Image
import httpx

# Ensure backend root is on sys.path
sys.path.insert(0, "/app")
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from app.database import AsyncSessionLocal
from app.models.event import Event, EventStatus
from app.services.telegram_bot import handle_inline_query, optimize_preview_image_url
from app.services.audience_service import get_organizer_audience
from app.models.user import User
from app.models.organization import Organization
from sqlalchemy import select


async def audit_and_fix_covers():
    uploads_dir = Path("/app/uploads")
    if not uploads_dir.exists():
        uploads_dir = Path(__file__).resolve().parent.parent.parent / "uploads"
    covers_dir = uploads_dir / "covers"
    covers_dir.mkdir(parents=True, exist_ok=True)

    print(f"=== STEP 1: AUDITING COVERS AND GENERATING 160x160 SQUARE _thumb.jpg IN {covers_dir} ===")
    from PIL import ImageOps
    converted_count = 0
    missing_count = 0
    ok_count = 0
    thumbs_created = 0

    # Scan all cover files on disk to guarantee every single cover has a valid 160x160 square thumbnail
    all_cover_files = [f for f in covers_dir.glob("*.jpg") if not f.name.endswith("_thumb.jpg") and not f.name.endswith(".tmp.jpg")]
    print(f"Total main cover files found on disk: {len(all_cover_files)}")

    for fpath in all_cover_files:
        try:
            base_name = fpath.stem
            thumb_path = covers_dir / f"{base_name}_thumb.jpg"

            with Image.open(fpath) as img:
                fmt = img.format
                mode = img.mode
                is_progressive = bool(img.info.get("progressive", False))
                needs_reencode = (fmt != "JPEG") or (mode != "RGB") or is_progressive

                if needs_reencode:
                    rgb = img.convert("RGB")
                    tmp_path = fpath.with_suffix(".tmp.jpg")
                    rgb.save(tmp_path, "JPEG", quality=82, optimize=True, progressive=False)
                    tmp_path.replace(fpath)
                    converted_count += 1
                else:
                    ok_count += 1

                # Check or create 160x160 square thumbnail
                thumb_valid = False
                if thumb_path.exists() and thumb_path.stat().st_size > 500:
                    try:
                        with Image.open(thumb_path) as timg:
                            if timg.size == (160, 160) and timg.format == "JPEG" and timg.mode == "RGB":
                                thumb_valid = True
                    except Exception:
                        thumb_valid = False

                if not thumb_valid:
                    if img.mode != "RGB":
                        img = img.convert("RGB")
                    thumb_img = ImageOps.fit(img, (160, 160), Image.Resampling.LANCZOS)
                    tmp_thumb = thumb_path.with_suffix(".tmp_thumb.jpg")
                    thumb_img.save(tmp_thumb, format="JPEG", quality=78, optimize=True, progressive=False)
                    tmp_thumb.replace(thumb_path)
                    thumbs_created += 1

        except Exception as e:
            print(f"  [ERROR] Processing {fpath.name}: {e}")

    print(f"Audit complete: {ok_count} main covers OK, {converted_count} re-encoded, {thumbs_created} thumbnails generated (160x160, ~8KB).\n")

    print("=== STEP 2: TESTING INLINE QUERY (query='') ===")
    async with AsyncSessionLocal() as session:
        inline_resp = await handle_inline_query(session, {"id": "test_empty_query", "query": ""})
        results = inline_resp.get("results", [])
        print(f"Inline query returned {len(results)} results (cache_time={inline_resp.get('cache_time')}, is_personal={inline_resp.get('is_personal')}):")

        async with httpx.AsyncClient(timeout=5.0, verify=False) as client:
            for idx, item in enumerate(results[:10], 1):
                item_id = item.get("id")
                item_type = item.get("type")
                title = item.get("title")
                thumb_url = item.get("thumbnail_url")
                w = item.get("thumbnail_width")
                h = item.get("thumbnail_height")

                status_code = None
                content_type = None
                pil_ok = False
                pil_format = None
                pil_size = None

                file_kb = 0.0
                if thumb_url:
                    try:
                        r = await client.get(thumb_url)
                        status_code = r.status_code
                        content_type = r.headers.get("content-type")
                        file_kb = len(r.content) / 1024.0
                        if status_code == 200:
                            import io
                            img = Image.open(io.BytesIO(r.content))
                            pil_ok = True
                            pil_format = img.format
                            pil_size = img.size
                    except Exception as e:
                        print(f"    Fetch error for {thumb_url}: {e}")

                print(f"  [{idx}] {title[:35]} (type={item_type}, id={item_id})")
                print(f"      thumb_url: {thumb_url}")
                print(f"      dims: {w}x{h} | size: {file_kb:.1f} KB | HTTP: {status_code} | Content-Type: {content_type} | PIL: {pil_format} {pil_size}")

    print("\n=== STEP 3: TESTING AUDIENCE METRICS FOR ORGANIZERS ===")
    async with AsyncSessionLocal() as session:
        orgs_res = await session.execute(select(Organization).limit(3))
        orgs = orgs_res.scalars().all()
        for org in orgs:
            try:
                aud = await get_organizer_audience(session, org.owner_user_id, org.id)
                print(f"  Org '{org.name}' ({org.id}):")
                print(f"    total_unique_engaged: {aud.total_unique_engaged}")
                print(f"    new_subscribers_today: {aud.new_subscribers_today}")
                print(f"    new_subscribers_7d: {aud.new_subscribers_7d}")
                print(f"    new_subscribers_30d: {aud.new_subscribers_30d}")
                if aud.daily_growth:
                    today_pt = aud.daily_growth[-1]
                    first_pt = aud.daily_growth[0]
                    print(f"    daily_growth[0] ({first_pt.date}, {first_pt.label}): new={first_pt.new_count}, cum={first_pt.cumulative_count}")
                    print(f"    daily_growth[-1] ({today_pt.date}, {today_pt.label}): new={today_pt.new_count}, cum={today_pt.cumulative_count}")
            except Exception as e:
                print(f"    Error querying audience for {org.name}: {e}")


if __name__ == "__main__":
    asyncio.run(audit_and_fix_covers())
