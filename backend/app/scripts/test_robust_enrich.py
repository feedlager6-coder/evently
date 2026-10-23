import asyncio
import re
import json
import httpx

async def test():
    async with httpx.AsyncClient(headers={"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"}, follow_redirects=True) as client:
        resp = await client.get("https://afisha.yandex.ru/makhachkala/concert/arslan-shakhmardanov")
        print("status:", resp.status_code)
        print("final url:", resp.url)
        
        # Check ld+json
        ld_matches = re.findall(r'<script[^>]*type=[\'"]application/ld\+json[\'"][^>]*>(.*?)</script>', resp.text, re.DOTALL)
        for ld in ld_matches:
            try:
                data = json.loads(ld)
                print("ld+json:", data.get("@type"), data.get("name"), "startDate:", data.get("startDate"), "image:", data.get("image"))
            except Exception as e:
                pass
                
        # Check og:image
        og_img = re.search(r'<meta\s+property=[\'"]og:image[\'"]\s+content=[\'"](.*?)[\'"]', resp.text)
        print("og:image:", og_img.group(1) if og_img else None)
        
        # Check Apollo
        ev_m = re.search(r'window\[[\'"]__APOLLO_STATE__[\'"]\]\s*=\s*(.*?);\s*</script>', resp.text, re.DOTALL)
        if ev_m:
            raw = ev_m.group(1)
            clean = re.sub(r'new Date\([^)]+\)', '"2026-10-23T00:00:00Z"', raw)
            clean = re.sub(r'\bundefined\b', 'null', clean)
            ap = json.loads(clean)
            print("Apollo total keys:", len(ap))
            for k, v in ap.items():
                if isinstance(v, dict):
                    if v.get("__typename") == "Event":
                        print("Found Event in Apollo:", k, v.get("title"), "image:", v.get("image"), "featuredImage:", v.get("featuredImage"))
                    if "eventScheduleInfo" in k:
                        print("Found eventScheduleInfo key:", k, json.dumps(v, ensure_ascii=False)[:300])

asyncio.run(test())
