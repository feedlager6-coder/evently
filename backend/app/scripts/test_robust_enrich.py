import asyncio
import re
import json
import httpx

async def test():
    async with httpx.AsyncClient(headers={"User-Agent": "Mozilla/5.0"}) as client:
        resp = await client.get("https://afisha.yandex.ru/makhachkala/concert/shaman-30-let-na-stsene")
        ev_m = re.search(r"window\[[\x27\"]__APOLLO_STATE__[\x27\"]\]\s*=\s*(.*?);\s*</script>", resp.text, re.DOTALL)
        if ev_m:
            raw = ev_m.group(1)
            clean = re.sub(r"new Date\([^)]+\)", '"2026-10-23T00:00:00Z"', raw)
            clean = re.sub(r"\bundefined\b", "null", clean)
            ap = json.loads(clean)
            rq = ap.get("ROOT_QUERY", {})
            for rk, rv in rq.items():
                if "eventScheduleInfo" in rk:
                    print(f"eventScheduleInfo:\n{json.dumps(rv, ensure_ascii=False, indent=2)}")

asyncio.run(test())
