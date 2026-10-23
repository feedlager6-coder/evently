import asyncio
import re
import json
import httpx

async def test():
    async with httpx.AsyncClient(headers={"User-Agent": "Mozilla/5.0"}) as client:
        resp = await client.get("https://afisha.yandex.ru/makhachkala/concert/shaman-30-let-na-stsene")
        html = resp.text
        idx = html.find("6 ноября, 19:00")
        # Find enclosing json key: find last '"key": {' before idx
        print("Surrounding 300 chars before idx:\n", html[idx-300:idx])
        print("Surrounding 200 chars after idx:\n", html[idx:idx+200])

asyncio.run(test())
