from typing import Dict, List, Optional
import re

# Mapping from Ivently city_id to Kassir.ru subdomain
KASSIR_CITY_SUBDOMAINS: Dict[str, str] = {
    "moscow": "msk",
    "spb": "spb",
    "makhachkala": "dagestan",
    "derbent": "dagestan",
    "kaspiysk": "dagestan",
    "khasavyurt": "dagestan",
    "izberbash": "dagestan",
    "kazan": "kzn",
    "krasnodar": "krd",
    "sochi": "sochi",
    "rostov_on_don": "rnd",
    "yekaterinburg": "ekb",
    "novosibirsk": "nsk",
    "nizhny_novgorod": "nn",
    "samara": "smr",
    "ufa": "ufa",
    "krasnoyarsk": "krsk",
    "voronezh": "vrn",
    "volgograd": "volgograd",
    "saratov": "saratov",
    "tolyatti": "tlt",
    "izhevsk": "izhevsk",
    "barnaul": "barnaul",
    "irkutsk": "irkutsk",
    "khabarovsk": "habarovsk",
    "vladivostok": "vld",
    "kaliningrad": "kaliningrad",
    "yaroslavl": "yaroslavl",
    "chelyabinsk": "chelyabinsk",
    "tyumen": "tmn",
    "omsk": "omsk",
    "perm": "perm",
    "orenburg": "orenburg",
    "ryazan": "rzn",
    "penza": "penza",
    "naberezhnye_chelny": "chelny",
    "lipetsk": "lipetsk",
    "tula": "tula",
    "kirov": "kirov",
    "cheboksary": "cheboksary",
    "kursk": "kursk",
    "tver": "tver",
    "ivanovo": "ivanovo",
    "bryansk": "bryansk",
    "belgorod": "belgorod",
    "vologda": "vologda",
    "cherepovets": "cherepovets",
    "astrakhan": "astrakhan",
    "stavropol": "stavropol",
    "pyatigorsk": "pyatigorsk",
    "essentuki": "pyatigorsk",
    "kislovodsk": "pyatigorsk",
    "arkhangelsk": "arh",
    "murmansk": "murmansk",
    "petrozavodsk": "ptz",
    "surgut": "surgut",
    "nizhnevartovsk": "nvartovsk",
    "kurgan": "kurgan",
    "magnitogorsk": "mgn",
    "nizhniy_tagil": "tagil",
    "sterlitamak": "sterlitamak",
    "tomsk": "tomsk",
    "kemerovo": "kemerovo",
    "novokuznetsk": "nvkz",
    "ulan_ude": "ulanude",
    "chita": "chita",
    "yakutsk": "yakutsk",
    "blagoveshchensk": "blagoveshensk",
    "kostroma": "kostroma",
    "vladimir": "vladimir",
    "kaluga": "kaluga",
    "oryol": "orel",
    "smolensk": "smolensk",
    "dzerzhinsk": "nn",
    "yoshkar_ola": "yo",
    "novorossiysk": "krd",
    "taganrog": "rnd",
    "cherkessk": "cherkessk",
    "nalchik": "nalchik",
    "vladikavkaz": "vladikavkaz",
    "grozny": "grozny",
    "saransk": "saransk",
    "tambov": "tambov",
    "petropavlovsk_kamchatskiy": "kamchatka",
    "yuzhno_sakhalinsk": "sakhalin",
}

# Mapping from Ivently city_id to MTS Live slug (strictly verified active cities on live.mts.ru)
# Regional cities without native MTS Live presence (Makhachkala, Derbent, Grozny, etc.) are excluded
# to prevent silent fallback to Moscow events.
MTS_CITY_SLUGS: Dict[str, str] = {
    "moscow": "moscow",
    "spb": "sankt-peterburg",
    "kazan": "kazan",
    "krasnodar": "krasnodar",
    "sochi": "sochi",
    "rostov_on_don": "rostov-na-donu",
    "novosibirsk": "novosibirsk",
    "samara": "samara",
    "ufa": "ufa",
    "krasnoyarsk": "krasnoyarsk",
    "voronezh": "voronezh",
    "volgograd": "volgograd",
    "saratov": "saratov",
    "izhevsk": "izhevsk",
    "barnaul": "barnaul",
    "irkutsk": "irkutsk",
    "vladivostok": "vladivostok",
    "kaliningrad": "kaliningrad",
    "yaroslavl": "yaroslavl",
    "chelyabinsk": "chelyabinsk",
    "tyumen": "tyumen",
    "omsk": "omsk",
    "perm": "perm",
    "orenburg": "orenburg",
    "ryazan": "ryazan",
    "tula": "tula",
    "tver": "tver",
    "ivanovo": "ivanovo",
    "stavropol": "stavropol",
    "tomsk": "tomsk",
    "kemerovo": "kemerovo",
    "novokuznetsk": "novokuznetsk",
    "vladimir": "vladimir",
    "kaluga": "kaluga",
}

# Mapping from Ivently city_id to Yandex.Afisha slug
YANDEX_CITY_SLUGS: Dict[str, str] = {
    "moscow": "moscow",
    "spb": "saint-petersburg",
    "makhachkala": "makhachkala",
    "derbent": "derbent",
    "kaspiysk": "kaspiysk",
    "kazan": "kazan",
    "krasnodar": "krasnodar",
    "sochi": "sochi",
    "rostov_on_don": "rostov-na-donu",
    "yekaterinburg": "yekaterinburg",
    "novosibirsk": "novosibirsk",
    "nizhny_novgorod": "nizhny-novgorod",
    "samara": "samara",
    "ufa": "ufa",
    "krasnoyarsk": "krasnoyarsk",
    "voronezh": "voronezh",
    "volgograd": "volgograd",
    "saratov": "saratov",
    "tolyatti": "tolyatti",
    "izhevsk": "izhevsk",
    "barnaul": "barnaul",
    "irkutsk": "irkutsk",
    "khabarovsk": "khabarovsk",
    "vladivostok": "vladivostok",
    "kaliningrad": "kaliningrad",
    "yaroslavl": "yaroslavl",
    "chelyabinsk": "chelyabinsk",
    "tyumen": "tyumen",
    "omsk": "omsk",
    "perm": "perm",
    "orenburg": "orenburg",
    "ryazan": "ryazan",
    "penza": "penza",
    "naberezhnye_chelny": "naberezhnye-chelny",
    "lipetsk": "lipetsk",
    "tula": "tula",
    "kirov": "kirov",
    "cheboksary": "cheboksary",
    "kursk": "kursk",
    "tver": "tver",
    "ivanovo": "ivanovo",
    "bryansk": "bryansk",
    "belgorod": "belgorod",
    "vologda": "vologda",
    "cherepovets": "cherepovets",
    "astrakhan": "astrakhan",
    "stavropol": "stavropol",
    "pyatigorsk": "pyatigorsk",
    "essentuki": "essentuki",
    "kislovodsk": "kislovodsk",
    "arkhangelsk": "arkhangelsk",
    "murmansk": "murmansk",
    "petrozavodsk": "petrozavodsk",
    "surgut": "surgut",
    "nizhnevartovsk": "nizhnevartovsk",
    "kurgan": "kurgan",
    "magnitogorsk": "magnitogorsk",
    "nizhniy_tagil": "nizhny-tagil",
    "sterlitamak": "sterlitamak",
    "tomsk": "tomsk",
    "kemerovo": "kemerovo",
    "novokuznetsk": "novokuznetsk",
    "ulan_ude": "ulan-ude",
    "chita": "chita",
    "yakutsk": "yakutsk",
    "blagoveshchensk": "blagoveshchensk",
    "kostroma": "kostroma",
    "vladimir": "vladimir",
    "kaluga": "kaluga",
    "oryol": "oryol",
    "smolensk": "smolensk",
    "yoshkar_ola": "yoshkar-ola",
    "novorossiysk": "novorossiysk",
    "taganrog": "taganrog",
    "cherkessk": "cherkessk",
    "nalchik": "nalchik",
    "vladikavkaz": "vladikavkaz",
    "grozny": "grozny",
    "saransk": "saransk",
    "tambov": "tambov",
    "petropavlovsk_kamchatskiy": "petropavlovsk-kamchatsky",
    "yuzhno_sakhalinsk": "yuzhno-sakhalinsk",
}

# Substring matches in venue address/name to city_id
CITY_TEXT_MATCHERS: List[tuple[re.Pattern, str]] = [
    (re.compile(r'\bмахачкал[а-я]*\b', re.I), "makhachkala"),
    (re.compile(r'\bдербент[а-я]*\b', re.I), "derbent"),
    (re.compile(r'\bкаспийск[а-я]*\b', re.I), "kaspiysk"),
    (re.compile(r'\bхасавюрт[а-я]*\b', re.I), "khasavyurt"),
    (re.compile(r'\bизбербаш[а-я]*\b', re.I), "izberbash"),
    (re.compile(r'\bмоскв[а-я]*\b', re.I), "moscow"),
    (re.compile(r'\bсанкт-петербург[а-я]*\b|\bпетербург[а-я]*\b|\bпитер[а-я]*\b', re.I), "spb"),
    (re.compile(r'\bказан[ьиеяю]*\b', re.I), "kazan"),
    (re.compile(r'\bкраснодар[а-я]*\b', re.I), "krasnodar"),
    (re.compile(r'\bсочи\b', re.I), "sochi"),
    (re.compile(r'\bростов[а-я]*\b', re.I), "rostov_on_don"),
    (re.compile(r'\bекатеринбург[а-я]*\b', re.I), "yekaterinburg"),
    (re.compile(r'\bновосибирск[а-я]*\b', re.I), "novosibirsk"),
    (re.compile(r'\bнижн[иея]+й?\s*новгород[а-я]*\b', re.I), "nizhny_novgorod"),
    (re.compile(r'\bсамар[а-я]*\b', re.I), "samara"),
    (re.compile(r'\bуф[а-я]*\b', re.I), "ufa"),
    (re.compile(r'\bкрасноярск[а-я]*\b', re.I), "krasnoyarsk"),
    (re.compile(r'\bгрозн[а-я]*\b', re.I), "grozny"),
    (re.compile(r'\bвладикавказ[а-я]*\b', re.I), "vladikavkaz"),
    (re.compile(r'\bнальчик[а-я]*\b', re.I), "nalchik"),
    (re.compile(r'\bпятигорск[а-я]*\b', re.I), "pyatigorsk"),
    (re.compile(r'\bессентук[а-я]*\b', re.I), "essentuki"),
    (re.compile(r'\bкисловодск[а-я]*\b', re.I), "kislovodsk"),
    (re.compile(r'\bставропол[а-я]*\b', re.I), "stavropol"),
    (re.compile(r'\bволгоград[а-я]*\b', re.I), "volgograd"),
    (re.compile(r'\bсаратов[а-я]*\b', re.I), "saratov"),
    (re.compile(r'\bворонеж[а-я]*\b', re.I), "voronezh"),
    (re.compile(r'\bперм[ьиеяю]*\b', re.I), "perm"),
    (re.compile(r'\bчелябинск[а-я]*\b', re.I), "chelyabinsk"),
    (re.compile(r'\bтюмен[ьиеяю]*\b', re.I), "tyumen"),
    (re.compile(r'\bомск[а-я]*\b', re.I), "omsk"),
    (re.compile(r'\bиркутск[а-я]*\b', re.I), "irkutsk"),
    (re.compile(r'\bхабаровск[а-я]*\b', re.I), "khabarovsk"),
    (re.compile(r'\bвладивосток[а-я]*\b', re.I), "vladivostok"),
    (re.compile(r'\bкалининград[а-я]*\b', re.I), "kaliningrad"),
    (re.compile(r'\bярославл[а-я]*\b', re.I), "yaroslavl"),
    (re.compile(r'\bтольятт[а-я]*\b', re.I), "tolyatti"),
    (re.compile(r'\bижевск[а-я]*\b', re.I), "izhevsk"),
    (re.compile(r'\bульяновск[а-я]*\b', re.I), "ulyanovsk"),
    (re.compile(r'\bоренбург[а-я]*\b', re.I), "orenburg"),
    (re.compile(r'\bрязан[ьиеяю]*\b', re.I), "ryazan"),
    (re.compile(r'\bпенз[а-я]*\b', re.I), "penza"),
    (re.compile(r'\bнабережные челны\b|\bчелн[а-я]*\b', re.I), "naberezhnye_chelny"),
    (re.compile(r'\bлипецк[а-я]*\b', re.I), "lipetsk"),
    (re.compile(r'\bтул[а-я]*\b', re.I), "tula"),
    (re.compile(r'\bкиров[а-я]*\b', re.I), "kirov"),
    (re.compile(r'\bчебоксар[а-я]*\b', re.I), "cheboksary"),
    (re.compile(r'\bкурск[а-я]*\b', re.I), "kursk"),
    (re.compile(r'\bтвер[ьиеяю]*\b', re.I), "tver"),
    (re.compile(r'\bиванов[а-я]*\b', re.I), "ivanovo"),
    (re.compile(r'\bбрянск[а-я]*\b', re.I), "bryansk"),
    (re.compile(r'\bбелгород[а-я]*\b', re.I), "belgorod"),
    (re.compile(r'\bвологд[а-я]*\b', re.I), "vologda"),
    (re.compile(r'\bчереповец[а-я]*\b', re.I), "cherepovets"),
    (re.compile(r'\bастрахан[ьиеяю]*\b', re.I), "astrakhan"),
    (re.compile(r'\bархангельск[а-я]*\b', re.I), "arkhangelsk"),
    (re.compile(r'\bмурманск[а-я]*\b', re.I), "murmansk"),
    (re.compile(r'\bпетрозаводск[а-я]*\b', re.I), "petrozavodsk"),
    (re.compile(r'\bсургут[а-я]*\b', re.I), "surgut"),
    (re.compile(r'\bнижневартовск[а-я]*\b', re.I), "nizhnevartovsk"),
    (re.compile(r'\bкурган[а-я]*\b', re.I), "kurgan"),
    (re.compile(r'\bмагнитогорск[а-я]*\b', re.I), "magnitogorsk"),
    (re.compile(r'\bнижн[иея]+й?\s*тагил[а-я]*\b', re.I), "nizhniy_tagil"),
    (re.compile(r'\bстерлитамак[а-я]*\b', re.I), "sterlitamak"),
    (re.compile(r'\bбарнаул[а-я]*\b', re.I), "barnaul"),
    (re.compile(r'\bтомск[а-я]*\b', re.I), "tomsk"),
    (re.compile(r'\bкемеров[а-я]*\b', re.I), "kemerovo"),
    (re.compile(r'\bновокузнецк[а-я]*\b', re.I), "novokuznetsk"),
    (re.compile(r'\bулан-удэ\b', re.I), "ulan_ude"),
    (re.compile(r'\bчит[а-я]*\b', re.I), "chita"),
    (re.compile(r'\bякутск[а-я]*\b', re.I), "yakutsk"),
    (re.compile(r'\bблаговещенск[а-я]*\b', re.I), "blagoveshchensk"),
    (re.compile(r'\bкостром[а-я]*\b', re.I), "kostroma"),
    (re.compile(r'\bвладимир[а-я]*\b', re.I), "vladimir"),
    (re.compile(r'\bкалуг[а-я]*\b', re.I), "kaluga"),
    (re.compile(r'\bор[её]л[а-я]*\b|\bорловск[а-я]*\b', re.I), "oryol"),
    (re.compile(r'\bсмоленск[а-я]*\b', re.I), "smolensk"),
    (re.compile(r'\bдзержинск[а-я]*\b', re.I), "dzerzhinsk"),
    (re.compile(r'\bйошкар-ола\b', re.I), "yoshkar_ola"),
    (re.compile(r'\bновороссийск[а-я]*\b', re.I), "novorossiysk"),
    (re.compile(r'\bтаганрог[а-я]*\b', re.I), "taganrog"),
    (re.compile(r'\bчеркесск[а-я]*\b', re.I), "cherkessk"),
    (re.compile(r'\bсаранск[а-я]*\b', re.I), "saransk"),
    (re.compile(r'\bтамбов[а-я]*\b', re.I), "tambov"),
    (re.compile(r'\bпетропавловск-камчатск[а-я]*\b', re.I), "petropavlovsk_kamchatskiy"),
    (re.compile(r'\bюжно-сахалинск[а-я]*\b', re.I), "yuzhno_sakhalinsk"),
]


def resolve_city_from_text(text: str, default_city_id: Optional[str] = None) -> Optional[str]:
    """
    Extracts the most accurate city_id from venue name, address, or city text.
    """
    if not text:
        return default_city_id

    for pattern, city_id in CITY_TEXT_MATCHERS:
        if pattern.search(text):
            return city_id

    return default_city_id


# ---------------------------------------------------------
# Anti-Geo-Spoofing & Geo-Leakage Validation
# ---------------------------------------------------------

_MOSCOW_SPOOF_PATTERN = re.compile(
    r'(?<![а-яёa-z])(?:'
    r'москв[а-я]*|лужники|втб\s+арен[а-я]*|live\s+арен[а-я]*|дворец\s+ирины\s+винер|'
    r'цска\s+арен[а-я]*|ммдм|бкз\s+космос|театр\s+на\s+страстном|театр\s+сатиры|'
    r'мастерск[а-я]*\s+петра\s+фоменко|крокус|зарядье|москва\s+202\d|подольск|мытищи|балаших[а-я]*|'
    r'красн[а-я]*\s+пресн[а-я]*|чистые\s+пруды|тверск[а-я]*\s+улиц[а-я]*|арбат'
    r')(?![а-яёa-z])',
    re.IGNORECASE
)

_SPB_SPOOF_PATTERN = re.compile(
    r'(?<![а-яёa-z])(?:'
    r'санкт-петербург[а-я]*|петербург[а-я]*|питер[а-я]*|газпром\s+арен[а-я]*|'
    r'бкз\s+октябрьск[а-я]*|ледовый\s+дворец\s+спб|мариинск[а-я]*\s+театр[а-я]*|'
    r'михайловск[а-я]*\s+театр[а-я]*|александринск[а-я]*\s+театр[а-я]*|эрмитаж[а-я]*|петергоф[а-я]*|'
    r'невск[а-я]*\s+проспект|васильевск[а-я]*\s+остров'
    r')(?![а-яёa-z])',
    re.IGNORECASE
)

_OTHER_REGIONS_PATTERN = re.compile(
    r'(?<![а-яёa-z])(?:'
    r'казан[ьиеяю]*|краснодар[а-я]*|сочи|екатеринбург[а-я]*|новосибирск[а-я]*|самар[а-я]*|'
    r'нижн[иея]+й?\s*новгород[а-я]*|уф[а-я]*|воронеж[а-я]*|волгоград[а-я]*|ростов[а-я]*|'
    r'перм[ьиеяю]*|омск[а-я]*|томск[а-я]*|красноярск[а-я]*|челябинск[а-я]*|тюмен[ьиеяю]*|'
    r'ульяновск[а-я]*|ярославл[а-я]*|иркутск[а-я]*|барнаул[а-я]*|владивосток[а-я]*|хабаровск[а-я]*'
    r')(?![а-яёa-z])',
    re.IGNORECASE
)

DAGESTAN_CITIES = {"makhachkala", "derbent", "kaspiysk", "khasavyurt", "izberbash"}


def validate_event_city(
    source_name: str,
    source_url: Optional[str],
    title: str,
    venue_name: str,
    address: str,
    target_city_id: str,
) -> bool:
    """
    Strict Anti-Geo-Spoofing validator.
    Prevents events from Moscow, Saint Petersburg or other cities from leaking into regional city feeds.
    Checks URL domain/slug integrity and text/venue geographic consistency.
    """
    target_city_id = (target_city_id or "").lower()
    clean_url = (source_url or "").lower()
    full_text = f"{title} {venue_name} {address}".lower()

    # 1. URL Domain & Slug validation
    if clean_url:
        # A. Yandex.Afisha check
        if "afisha.yandex.ru" in clean_url:
            if target_city_id != "moscow" and ("/moscow/" in clean_url or "/msk/" in clean_url):
                return False
            if target_city_id != "spb" and ("/saint-petersburg/" in clean_url or "/spb/" in clean_url):
                return False

            if target_city_id in DAGESTAN_CITIES:
                # Must be one of Dagestan Yandex slugs
                if not any(f"/{dag_slug}/" in clean_url for dag_slug in ["makhachkala", "derbent", "kaspiysk"]):
                    return False
            elif target_city_id in YANDEX_CITY_SLUGS:
                expected_slug = YANDEX_CITY_SLUGS[target_city_id]
                if f"/{expected_slug}/" not in clean_url:
                    return False

        # B. Kassir.ru check
        elif "kassir.ru" in clean_url:
            if target_city_id != "moscow" and "msk.kassir.ru" in clean_url:
                return False
            if target_city_id != "spb" and "spb.kassir.ru" in clean_url:
                return False

            if target_city_id in DAGESTAN_CITIES:
                if "dagestan.kassir.ru" not in clean_url:
                    return False
            elif target_city_id in KASSIR_CITY_SUBDOMAINS:
                expected_sub = KASSIR_CITY_SUBDOMAINS[target_city_id]
                if f"{expected_sub}.kassir.ru" not in clean_url:
                    return False

        # C. MTS Live check
        elif "live.mts.ru" in clean_url:
            if target_city_id not in MTS_CITY_SLUGS:
                return False
            if target_city_id != "moscow" and "/moscow/" in clean_url:
                return False
            expected_slug = MTS_CITY_SLUGS[target_city_id]
            if f"/{expected_slug}/" not in clean_url:
                return False

    # 2. Text inspection: check for foreign city names / landmarks
    if target_city_id != "moscow":
        if _MOSCOW_SPOOF_PATTERN.search(full_text):
            return False

    if target_city_id != "spb":
        if _SPB_SPOOF_PATTERN.search(full_text):
            return False

    # 3. Dagestan intra-region integrity
    if target_city_id in DAGESTAN_CITIES:
        if _OTHER_REGIONS_PATTERN.search(full_text):
            return False

        # Do not put events clearly held in Derbent into Makhachkala, etc.
        if target_city_id == "makhachkala":
            if "г. дербент" in address or "в дербенте" in full_text:
                return False
        elif target_city_id == "derbent":
            if "г. махачкала" in address or "в махачкале" in full_text:
                return False
        elif target_city_id == "kaspiysk":
            if "г. махачкала" in address or "в махачкале" in full_text:
                return False

    return True

