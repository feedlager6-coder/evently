import asyncio
import re
import json
import httpx

def inspect_event(url):
    print(f"\n================ INSPECTING: {url} ================")
    headers = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) Chrome/129.0"}
    resp = httpx.get(url, headers=headers)
    print("STATUS:", resp.status_code)
    html = resp.text
    
    # 1. ld+json
    ld_blocks = re.findall(r'<script type="application/ld\+json"[^>]*>(.*?)</script>', html, re.DOTALL)
    for i, b in enumerate(ld_blocks):
        try:
            d = json.loads(b)
            if d.get("@type") in ("Event", "MusicEvent", "TheaterEvent"):
                print(f"--- LD+JSON Event ---")
                print("Type:", d.get("@type"))
                print("Name:", d.get("name"))
                print("startDate:", d.get("startDate"))
                print("endDate:", d.get("endDate"))
                print("location:", d.get("location", {}).get("name") if isinstance(d.get("location"), dict) else d.get("location"))
                print("image:", d.get("image"))
        except Exception as e:
            pass

    # 2. og:image
    og_img = re.search(r'<meta property="og:image" content="([^"]+)"', html)
    print("OG:IMAGE:", og_img.group(1) if og_img else "None")

    # 3. ScheduleInfo / Dates from Apollo
    m = re.search(r"window\[[\'\"]__APOLLO_STATE__[\'\"]\]\s*=\s*(.*?);\s*</script>", html, re.DOTALL)
    if m:
        clean = re.sub(r"new Date\([^)]+\)", '"2026-10-23T00:00:00Z"', m.group(1))
        clean = re.sub(r"\bundefined\b", "null", clean)
        try:
            ap_data = json.loads(clean)
            for k, v in ap_data.items():
                if isinstance(v, dict):
                    tname = v.get("__typename")
                    if tname in ("Event", "ScheduleInfo", "ActualEvent", "EventPreview"):
                        for sched_key in ("regularity", "scheduleInfo", "singleShowtime", "preview", "sessions", "dates"):
                            if sched_key in v:
                                print(f"  Apollo [{k}] {sched_key}: {v[sched_key]}")
                    if tname == "Image":
                        print(f"  Apollo Image [{k}]: {v}")
        except Exception as e:
            print("Apollo parse error:", e)

    # 5. Look for target date and its enclosing element
    idx = html.find("6 ноября, 19:00")
    if idx != -1:
        print("\nFound '6 ноября, 19:00' snippet:\n", html[max(0, idx-150):idx+150])

    idx2 = html.find("2 ноября, 18:00")
    if idx2 != -1:
        print("\nFound '2 ноября, 18:00' snippet:\n", html[max(0, idx2-150):idx2+150])

def inspect():
    inspect_event("https://afisha.yandex.ru/makhachkala/concert/shaman-30-let-na-stsene")
    inspect_event("https://afisha.yandex.ru/makhachkala/concert/arslan-shakhmardanov")

if __name__ == "__main__":
    inspect()
