import asyncio
import re
import json
import httpx

async def test():
    async with httpx.AsyncClient(headers={"User-Agent": "Mozilla/5.0"}) as client:
        resp = await client.get("https://afisha.yandex.ru/makhachkala/concert/shaman-30-let-na-stsene")
        html = resp.text
        idx = html.find("6 ноября, 19:00")
        print("Found at index:", idx)
        # Search backwards for script tag
        script_start = html.rfind("<script", 0, idx)
        script_end = html.find("</script>", idx)
        print("Script tag header:", html[script_start:script_start+100])
        print("Total script len:", script_end - script_start)
        
        # Check if it is inside Apollo state or next/data
        script_content = html[script_start:script_end]
        if "__APOLLO_STATE__" in script_content:
            print("YES, it is inside __APOLLO_STATE__!")
        else:
            print("NO, it is inside another script tag!")

asyncio.run(test())
