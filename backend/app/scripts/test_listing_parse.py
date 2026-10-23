import asyncio
import httpx
import re
import json

async def test():
    async with httpx.AsyncClient(headers={"User-Agent": "Mozilla/5.0"}) as client:
        resp = await client.get("https://afisha.yandex.ru/makhachkala/concert")
        m = re.search(r"window\[[\'\"]__APOLLO_STATE__[\'\"]\]\s*=\s*(.*?);\s*</script>", resp.text, re.DOTALL)
        if m:
            clean = re.sub(r"new Date\([^)]+\)", '"2026-10-23T00:00:00Z"', m.group(1))
            clean = re.sub(r"\bundefined\b", "null", clean)
            ap = json.loads(clean)
            for k, v in ap.items():
                if isinstance(v, dict) and "шахмарданов" in str(v).lower():
                    print(f"Apollo [{k}]:\n{json.dumps(v, ensure_ascii=False, indent=2)}")

asyncio.run(test())
