import asyncio, httpx, json, sys

REGION_SLUGS_TO_CHECK = {
    "tula": ["tulskaya-oblast", "tula"],
    "bryansk": ["bryanskaya-oblast", "bryansk"],
    "tver": ["tverskaya-oblast", "tver"],
    "ivanovo": ["ivanovskaya-oblast", "ivanovo"],
    "vladimir": ["vladimirskaya-oblast", "vladimir"],
    "kostroma": ["kostromskaya-oblast", "kostroma"],
    "smolensk": ["smolenskaya-oblast", "smolensk"],
    "vologda": ["vologodskaya-oblast", "vologda"],
    "cherepovets": ["vologodskaya-oblast"],
    "kaluga": ["kaluzhskaya-oblast", "kaluga"],
    "oryol": ["orlovskaya-oblast", "orel"],
    "kursk": ["kurskaya-oblast", "kursk"],
    "tambov": ["tambovskaya-oblast", "tambov"],
    "arkhangelsk": ["arkhangelskaya-oblast", "arhangelsk"],
    "murmansk": ["murmanskaya-oblast", "murmansk"],
    "kurgan": ["kurganskaya-oblast", "kurgan"],
    "yuzhno_sakhalinsk": ["sahalinskaya-oblast", "yuzhno-sahalinsk"],
    "petropavlovsk_kamchatskiy": ["kamchatskiy-kray", "petropavlovsk-kamchatskiy"],
    "petrozavodsk": ["respublika-kareliya", "petrozavodsk"],
    "saransk": ["respublika-mordoviya", "saransk"],
    "cheboksary": ["chuvashskaya-respublika", "cheboksary"],
    "yoshkar_ola": ["respublika-mariy-el", "yoshkar-ola"],
    "yakutsk": ["respublika-saha-yakutiya", "yakutsk"],
    "ulan_ude": ["respublika-buryatiya", "ulan-ude"],
    "chita": ["zabaykalskiy-kray", "chita"],
    "blagoveshchensk": ["amurskaya-oblast", "blagoveshchensk"],
    "cherkessk": ["karachaevo-cherkesskaya-respublika", "cherkessk"],
    "kemerovo": ["kemerovskaya-oblast", "kemerovo"],
    "novokuznetsk": ["kemerovskaya-oblast", "novokuznetsk"],
    "tomsk": ["tomskaya-oblast", "tomsk"],
    "barnaul": ["altayskiy-kray", "barnaul"],
    "surgut": ["hanty-mansiyskiy-avtonomnyy-okrug-yugra", "surgut"],
    "nizhnevartovsk": ["hanty-mansiyskiy-avtonomnyy-okrug-yugra", "nizhnevartovsk"],
    "magnitogorsk": ["chelyabinskaya-oblast", "magnitogorsk"],
    "nizhniy_tagil": ["sverdlovskaya-oblast", "nizhniy-tagil"],
    "sterlitamak": ["respublika-bashkortostan", "sterlitamak"],
    "astrakhan": ["astrahanskaya-oblast", "astrakhan"],
    "novorossiysk": ["krasnodarskiy-kray", "novorossiysk"],
    "taganrog": ["rostovskaya-oblast", "taganrog"],
    "dzerzhinsk": ["nizhegorodskaya-oblast", "dzerzhinsk"],
    "essentuki": ["stavropolskiy-kray", "essentuki"],
    "kislovodsk": ["stavropolskiy-kray", "kislovodsk"],
}

async def check():
    headers = {'User-Agent': 'Mozilla/5.0'}
    async with httpx.AsyncClient(headers=headers, follow_redirects=True, timeout=10.0) as client:
        for cid, slugs in REGION_SLUGS_TO_CHECK.items():
            for slug in slugs:
                url = f"https://www.culture.ru/afisha/{slug}"
                try:
                    r = await client.get(url)
                    tag = '<script id="__NEXT_DATA__"'
                    idx = r.text.find(tag)
                    if idx != -1:
                        s = r.text.find('>', idx) + 1
                        e = r.text.find('</script>', s)
                        data = json.loads(r.text[s:e])
                        items = data.get('props', {}).get('pageProps', {}).get('events', {}).get('items', [])
                        # Check if items belong to this region and not nationwide fallback
                        if items:
                            first_loc = items[0].get('places', [{}])[0].get('locale', {})
                            first_name = first_loc.get('name') or first_loc.get('slug')
                            print(f"[OK] {cid} with {slug}: {len(items)} items (sample loc: {first_name})")
                            break
                except Exception as ex:
                    print(f"[ERR] {cid} {slug}: {ex}")
                await asyncio.sleep(0.3)

asyncio.run(check())
