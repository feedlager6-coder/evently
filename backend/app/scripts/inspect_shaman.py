import asyncio
import re
import json
import httpx

def inspect():
    url = "https://afisha.yandex.ru/makhachkala/concert/shaman-30-let-na-stsene"
    headers = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) Chrome/129.0"}
    resp = httpx.get(url, headers=headers)
    print("STATUS:", resp.status_code)
    html = resp.text
    
    # 1. ld+json
    ld_blocks = re.findall(r'<script type="application/ld\+json"[^>]*>(.*?)</script>', html, re.DOTALL)
    print(f"Found {len(ld_blocks)} ld+json blocks")
    for i, b in enumerate(ld_blocks):
        try:
            d = json.loads(b)
            print(f"--- LD+JSON block {i} ---")
            print("Type:", d.get("@type"))
            print("Name:", d.get("name"))
            print("startDate:", d.get("startDate"))
            print("endDate:", d.get("endDate"))
            print("location:", d.get("location"))
            print("image:", d.get("image"))
        except Exception as e:
            print(f"Error parsing ld+json {i}:", e)

    # 2. og:image
    og_img = re.search(r'<meta property="og:image" content="([^"]+)"', html)
    print("OG:IMAGE:", og_img.group(1) if og_img else "None")

    # 3. Apollo state scheduleInfo
    m = re.search(r"window\[[\'\"]__APOLLO_STATE__[\'\"]\]\s*=\s*(.*?);\s*</script>", html, re.DOTALL)
    if m:
        clean = re.sub(r"new Date\([^)]+\)", '"2026-10-23T00:00:00Z"', m.group(1))
        clean = re.sub(r"\bundefined\b", "null", clean)
        try:
            ap_data = json.loads(clean)
            for k, v in ap_data.items():
                if isinstance(v, dict):
                    if v.get("__typename") in ("Event", "ActualEvent", "ScheduleInfo", "Ticket"):
                        if "startDate" in v or "singleShowtime" in str(v) or "nearestDate" in str(v):
                            print(f"Apollo key {k} ({v.get('__typename')}): {v}")
        except Exception as e:
            print("Apollo state parse error:", e)

if __name__ == "__main__":
    inspect()
