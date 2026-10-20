import asyncio, httpx, json, re, sys
sys.path.insert(0, '/app/backend')
from app.database import AsyncSessionLocal
from app.models.city import City
from sqlalchemy import select

async def main():
    async with AsyncSessionLocal() as session:
        active = set((await session.execute(select(City.id).where(City.is_active == True))).scalars().all())
        headers = {'User-Agent': 'Mozilla/5.0'}
        async with httpx.AsyncClient(headers=headers, follow_redirects=True) as client:
            r = await client.get('https://www.culture.ru/afisha/tulskaya-oblast')
            tag = '<script id="__NEXT_DATA__"'
            idx = r.text.find(tag)
            s = r.text.find('>', idx) + 1
            e = r.text.find('</script>', s)
            data = json.loads(r.text[s:e])
            items = data.get('props', {}).get('pageProps', {}).get('events', {}).get('items', [])
            print('Tula items count:', len(items))
            for i, it in enumerate(items[:5]):
                places = it.get('places', [])
                p0 = places[0] if places else {}
                loc = p0.get('locale', {})
                loc_slug = loc.get('slug') if isinstance(loc, dict) else None
                loc_name = loc.get('name') if isinstance(loc, dict) else None
                addr = p0.get('address', {}).get('street') if isinstance(p0.get('address'), dict) else ''
                print(f'{i}: {it.get("name")} | loc: {loc_slug} ({loc_name}) | addr: {addr}')

asyncio.run(main())
