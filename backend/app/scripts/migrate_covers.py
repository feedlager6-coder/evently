import asyncio
import io
import os
import sys
from pathlib import Path
from PIL import Image, ImageOps
import httpx
from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession
from sqlalchemy.orm import sessionmaker

# Setup paths to import app modules if needed
backend_dir = Path(__file__).resolve().parent.parent.parent
sys.path.insert(0, str(backend_dir))

from app.config import settings
from app.models.event import Event


async def upload_to_catbox(content: bytes, filename: str) -> str:
    """Uploads JPEG bytes to Catbox CDN and returns public HTTPS URL."""
    async with httpx.AsyncClient(timeout=20.0) as client:
        files = {"fileToUpload": (filename, content, "image/jpeg")}
        data = {"reqtype": "fileupload"}
        resp = await client.post("https://catbox.moe/user/api.php", data=data, files=files)
        if resp.status_code == 200:
            url = resp.text.strip()
            if url.startswith("https://"):
                return url
        raise RuntimeError(f"Catbox upload failed: status={resp.status_code}, body={resp.text[:100]}")


async def optimize_image_bytes(raw_bytes: bytes) -> tuple[bytes, bytes]:
    """Optimizes image to 1200x800 progressive JPEG and generates 320x320 thumbnail."""
    with Image.open(io.BytesIO(raw_bytes)) as im:
        im = ImageOps.exif_transpose(im)
        im = im.convert("RGB")

        # 1. Main cover (max 1200x800)
        cover_im = im.copy()
        cover_im.thumbnail((1200, 800), Image.Resampling.LANCZOS)
        c_buf = io.BytesIO()
        cover_im.save(c_buf, format="JPEG", quality=82, optimize=True, progressive=True)
        cover_bytes = c_buf.getvalue()

        # 2. Square thumbnail (320x320)
        thumb_im = ImageOps.fit(im, (320, 320), Image.Resampling.LANCZOS)
        t_buf = io.BytesIO()
        thumb_im.save(t_buf, format="JPEG", quality=80, optimize=True)
        thumb_bytes = t_buf.getvalue()

        return cover_bytes, thumb_bytes


async def migrate_all_covers():
    engine = create_async_engine(settings.DATABASE_URL, echo=False)
    async_session = sessionmaker(engine, expire_on_commit=False, class_=AsyncSession)

    uploads_dir = Path(settings.STORAGE_LOCAL_DIR or "/app/uploads").resolve()
    covers_dir = uploads_dir / "covers"
    print(f"[*] Uploads covers dir: {covers_dir}")

    async with async_session() as session:
        result = await session.execute(select(Event))
        events = result.scalars().all()
        print(f"[*] Total events in DB: {len(events)}")

        migrated_count = 0
        for ev in events:
            cover_url = ev.cover_image_url
            if not cover_url:
                continue

            clean_url = cover_url.strip()
            # Check if this is a local cover or old url
            is_local = "/uploads/covers/" in clean_url
            is_old_concerts = "/covers/concerts.jpg" in clean_url or "/covers/default_event.jpg" in clean_url

            if is_old_concerts:
                print(f"[*] Updating placeholder event '{ev.title}' ({ev.id})...")
                ev.cover_image_url = "https://images.unsplash.com/photo-1514525253161-7a46d19cd819?w=800&h=500&auto=format&fit=crop&q=80"
                migrated_count += 1
                continue

            if not is_local:
                continue

            # Extract filename from url
            filename = clean_url.split("/uploads/covers/")[-1].split("?")[0]
            local_file = covers_dir / filename

            if not local_file.exists():
                print(f"[!] Warning: local file not found: {local_file} for event '{ev.title}'")
                continue

            print(f"[*] Processing '{ev.title}' (id={ev.id}, file={filename}, size={local_file.stat().st_size} bytes)...")
            raw_data = local_file.read_bytes()

            try:
                cover_bytes, thumb_bytes = await optimize_image_bytes(raw_data)
                # Save optimized files locally
                local_file.write_bytes(cover_bytes)
                thumb_file = covers_dir / f"{local_file.stem}_thumb.jpg"
                thumb_file.write_bytes(thumb_bytes)
                print(f"    Optimized local size: {len(cover_bytes)} bytes (thumb: {len(thumb_bytes)} bytes)")

                # Upload to public CDN
                cdn_url = await upload_to_catbox(cover_bytes, filename)
                print(f"    Uploaded to CDN: {cdn_url}")

                ev.cover_image_url = cdn_url
                migrated_count += 1
            except Exception as e:
                print(f"    [!] Error optimizing/uploading {filename}: {e}")

        await session.commit()
        print(f"[+] Migration complete! Updated {migrated_count} events.")


if __name__ == "__main__":
    asyncio.run(migrate_all_covers())
