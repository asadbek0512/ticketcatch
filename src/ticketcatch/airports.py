"""The airport directory the menu picks from and the free-text box searches.

Deliberately a curated list, not the full 40k IATA dump: a user needs the airports people actually
fly to, and every row here is one that returns fares from our sources. Anything missing can still
be typed as a raw IATA code — the search box accepts an unknown 3-letter code as-is, so an
incomplete list never becomes a wall.

Names are latin and written the way this bot's audience says them ("Toshkent", not "Tashkent");
`aliases` carries the other spellings so search finds the row either way.
"""

from dataclasses import dataclass

IATA_LENGTH = 3
MAX_RESULTS = 12  # a Telegram keyboard past ~12 rows is a scroll, not a choice

# Region id -> ordered airports. The id is an i18n key (region_kr, region_uz, ...), and order is
# "most likely first" rather than alphabetical, because the first row is the one people tap.
REGIONS: dict[str, tuple[tuple[str, str, str, tuple[str, ...]], ...]] = {
    # code, city, country, aliases
    "kr": (
        ("ICN", "Seul Incheon", "KR", ("seoul", "incheon", "korea", "koreya")),
        ("GMP", "Seul Gimpo", "KR", ("seoul", "gimpo", "kimpo")),
        ("PUS", "Busan", "KR", ("pusan",)),
        ("CJU", "Jeju", "KR", ("cheju",)),
        ("TAE", "Daegu", "KR", ("taegu",)),
    ),
    "uz": (
        ("TAS", "Toshkent", "UZ", ("tashkent", "uzbekistan", "ozbekiston")),
        ("SKD", "Samarqand", "UZ", ("samarkand",)),
        ("BHK", "Buxoro", "UZ", ("bukhara", "buhoro")),
        ("UGC", "Urganch", "UZ", ("urgench", "khiva", "xiva")),
        ("FEG", "Farg'ona", "UZ", ("fergana", "fargona")),
        ("NMA", "Namangan", "UZ", ()),
        ("AZN", "Andijon", "UZ", ("andijan",)),
        ("KSQ", "Qarshi", "UZ", ("karshi",)),
        ("TMJ", "Termiz", "UZ", ("termez",)),
        ("NCU", "Nukus", "UZ", ()),
    ),
    "cis": (
        ("ALA", "Olmaota", "KZ", ("almaty", "alma-ata")),
        ("NQZ", "Ostona", "KZ", ("astana", "nur-sultan", "nursultan")),
        ("FRU", "Bishkek", "KG", ("frunze", "kyrgyzstan")),
        ("OSS", "O'sh", "KG", ("osh",)),
        ("DYU", "Dushanbe", "TJ", ("tajikistan",)),
        ("SVO", "Moskva Sheremetyevo", "RU", ("moscow", "sheremetyevo")),
        ("DME", "Moskva Domodedovo", "RU", ("moscow", "domodedovo")),
        ("VKO", "Moskva Vnukovo", "RU", ("moscow", "vnukovo")),
        ("LED", "Sankt-Peterburg", "RU", ("saint petersburg", "spb", "pulkovo")),
        ("KZN", "Qozon", "RU", ("kazan",)),
        ("OVB", "Novosibirsk", "RU", ()),
        ("GYD", "Boku", "AZ", ("baku", "azerbaijan")),
        ("EVN", "Yerevan", "AM", ("armenia",)),
        ("TBS", "Tbilisi", "GE", ("georgia",)),
        ("MSQ", "Minsk", "BY", ("belarus",)),
    ),
    "asia": (
        ("PEK", "Pekin Capital", "CN", ("beijing", "peking")),
        ("PKX", "Pekin Daxing", "CN", ("beijing", "daxing")),
        ("PVG", "Shanxay Pudong", "CN", ("shanghai", "pudong")),
        ("CAN", "Guanchjou", "CN", ("guangzhou", "canton")),
        ("URC", "Urumchi", "CN", ("urumqi",)),
        ("HKG", "Gonkong", "HK", ("hong kong", "hongkong")),
        ("TPE", "Taypey", "TW", ("taipei", "taiwan")),
        ("NRT", "Tokio Narita", "JP", ("tokyo", "narita", "japan")),
        ("HND", "Tokio Haneda", "JP", ("tokyo", "haneda")),
        ("KIX", "Osaka", "JP", ("kansai",)),
        ("BKK", "Bangkok", "TH", ("thailand", "suvarnabhumi")),
        ("SIN", "Singapur", "SG", ("singapore", "changi")),
        ("KUL", "Kuala-Lumpur", "MY", ("kuala lumpur", "malaysia")),
        ("HAN", "Hanoy", "VN", ("hanoi", "vietnam")),
        ("SGN", "Xoshimin", "VN", ("ho chi minh", "saigon")),
        ("MNL", "Manila", "PH", ("philippines",)),
        ("CGK", "Jakarta", "ID", ("indonesia", "soekarno")),
        ("DEL", "Dehli", "IN", ("delhi", "india")),
        ("BOM", "Mumbay", "IN", ("mumbai", "bombay")),
        ("ISB", "Islomobod", "PK", ("islamabad", "pakistan")),
        ("LHE", "Lahor", "PK", ("lahore",)),
        ("KTM", "Katmandu", "NP", ("kathmandu", "nepal")),
        ("ULN", "Ulan-Bator", "MN", ("ulaanbaatar", "mongolia")),
    ),
    "gulf": (
        ("IST", "Istanbul", "TR", ("turkey", "turkiya")),
        ("SAW", "Istanbul Sabiha", "TR", ("sabiha", "gokcen")),
        ("DXB", "Dubay", "AE", ("dubai", "uae", "emirates")),
        ("AUH", "Abu-Dabi", "AE", ("abu dhabi",)),
        ("SHJ", "Sharja", "AE", ("sharjah",)),
        ("DOH", "Doha", "QA", ("qatar",)),
        ("JED", "Jidda", "SA", ("jeddah", "saudi", "umra", "umrah")),
        ("MED", "Madina", "SA", ("medina", "madinah")),
        ("RUH", "Ar-Riyod", "SA", ("riyadh",)),
        ("KWI", "Quvayt", "KW", ("kuwait",)),
        ("BAH", "Bahrayn", "BH", ("bahrain",)),
        ("MCT", "Maskat", "OM", ("muscat", "oman")),
        ("AMM", "Ammon", "JO", ("amman", "jordan")),
        ("TLV", "Tel-Aviv", "IL", ("israel",)),
        ("CAI", "Qohira", "EG", ("cairo", "egypt")),
    ),
    "eu": (
        ("LHR", "London Heathrow", "GB", ("london", "heathrow", "uk")),
        ("LGW", "London Gatwick", "GB", ("london", "gatwick")),
        ("CDG", "Parij", "FR", ("paris", "charles de gaulle", "france")),
        ("FRA", "Frankfurt", "DE", ("germany", "germaniya")),
        ("MUC", "Myunxen", "DE", ("munich", "munchen")),
        ("BER", "Berlin", "DE", ()),
        ("AMS", "Amsterdam", "NL", ("schiphol", "netherlands")),
        ("BRU", "Bryussel", "BE", ("brussels", "belgium")),
        ("MAD", "Madrid", "ES", ("spain", "ispaniya")),
        ("BCN", "Barselona", "ES", ("barcelona",)),
        ("FCO", "Rim", "IT", ("rome", "fiumicino", "italy")),
        ("MXP", "Milan", "IT", ("milano", "malpensa")),
        ("VIE", "Vena", "AT", ("vienna", "austria")),
        ("ZRH", "Sirix", "CH", ("zurich", "switzerland")),
        ("GVA", "Jeneva", "CH", ("geneva",)),
        ("CPH", "Kopengagen", "DK", ("copenhagen", "denmark")),
        ("ARN", "Stokgolm", "SE", ("stockholm", "sweden")),
        ("OSL", "Oslo", "NO", ("norway",)),
        ("HEL", "Xelsinki", "FI", ("helsinki", "finland")),
        ("WAW", "Varshava", "PL", ("warsaw", "poland")),
        ("KRK", "Krakov", "PL", ("krakow",)),
        ("PRG", "Praga", "CZ", ("prague", "czech")),
        ("BUD", "Budapesht", "HU", ("budapest", "hungary")),
        ("OTP", "Buxarest", "RO", ("bucharest", "romania")),
        ("SOF", "Sofiya", "BG", ("sofia", "bulgaria")),
        ("ATH", "Afina", "GR", ("athens", "greece")),
        ("LIS", "Lissabon", "PT", ("lisbon", "portugal")),
        ("DUB", "Dublin", "IE", ("ireland",)),
        ("RIX", "Riga", "LV", ("latvia",)),
        ("TLL", "Tallin", "EE", ("tallinn", "estonia")),
        ("VNO", "Vilnyus", "LT", ("vilnius", "lithuania")),
        ("BEG", "Belgrad", "RS", ("belgrade", "serbia")),
    ),
    "am": (
        ("JFK", "Nyu-York JFK", "US", ("new york", "jfk", "usa", "amerika")),
        ("EWR", "Nyu-York Newark", "US", ("new york", "newark")),
        ("LAX", "Los-Anjeles", "US", ("los angeles",)),
        ("SFO", "San-Fransisko", "US", ("san francisco",)),
        ("ORD", "Chikago", "US", ("chicago", "o'hare")),
        ("IAD", "Vashington", "US", ("washington", "dulles")),
        ("ATL", "Atlanta", "US", ()),
        ("DFW", "Dallas", "US", ()),
        ("MIA", "Mayami", "US", ("miami",)),
        ("BOS", "Boston", "US", ()),
        ("SEA", "Sietl", "US", ("seattle",)),
        ("YYZ", "Toronto", "CA", ("canada", "kanada")),
        ("YVR", "Vankuver", "CA", ("vancouver",)),
        ("MEX", "Mexiko", "MX", ("mexico city",)),
        ("GRU", "San-Paulu", "BR", ("sao paulo", "brazil")),
        ("EZE", "Buenos-Ayres", "AR", ("buenos aires", "argentina")),
        ("LIM", "Lima", "PE", ("peru",)),
        ("BOG", "Bogota", "CO", ("colombia",)),
    ),
    "af": (
        ("CMN", "Kasablanka", "MA", ("casablanca", "morocco")),
        ("TUN", "Tunis", "TN", ("tunisia",)),
        ("ALG", "Aljir", "DZ", ("algiers", "algeria")),
        ("JNB", "Yoxannesburg", "ZA", ("johannesburg", "south africa")),
        ("CPT", "Keyptaun", "ZA", ("cape town",)),
        ("NBO", "Nayrobi", "KE", ("nairobi", "kenya")),
        ("ADD", "Addis-Abeba", "ET", ("addis ababa", "ethiopia")),
        ("LOS", "Lagos", "NG", ("nigeria",)),
        ("SYD", "Sidney", "AU", ("sydney", "australia")),
        ("MEL", "Melburn", "AU", ("melbourne",)),
        ("AKL", "Oklend", "NZ", ("auckland", "new zealand")),
    ),
}

# Shown on the first screen of the picker: this bot was built for the Korea ⇄ Uzbekistan run and
# most taps land here, so they skip the region step.
POPULAR = ("ICN", "TAS", "GMP", "SKD", "PUS", "NMA", "DXB", "IST", "ALA", "MED", "SVO", "FRU")


@dataclass(frozen=True)
class Airport:
    code: str
    city: str
    country: str
    region: str
    aliases: tuple[str, ...] = ()

    @property
    def label(self) -> str:
        return f"{self.city} ({self.code})"

    @property
    def haystack(self) -> str:
        return " ".join((self.code, self.city, self.country, *self.aliases)).lower()


AIRPORTS: dict[str, Airport] = {
    code: Airport(code=code, city=city, country=country, region=region, aliases=aliases)
    for region, rows in REGIONS.items()
    for code, city, country, aliases in rows
}


def get(code: str) -> Airport | None:
    return AIRPORTS.get(code.upper().strip())


def city(code: str) -> str:
    """Display name for a code, falling back to the code itself for airports we don't list."""
    found = get(code)
    return found.city if found else code.upper()


def label(code: str) -> str:
    found = get(code)
    return found.label if found else code.upper()


def in_region(region: str) -> list[Airport]:
    return [AIRPORTS[row[0]] for row in REGIONS.get(region, ())]


def popular() -> list[Airport]:
    return [AIRPORTS[c] for c in POPULAR if c in AIRPORTS]


def is_iata(text: str) -> bool:
    return len(text.strip()) == IATA_LENGTH and text.strip().isalpha()


def search(query: str, limit: int = MAX_RESULTS) -> list[Airport]:
    """Find airports by code, city or any known spelling.

    Ranked so the obvious answer is first: an exact code beats a city that starts with the query,
    which beats a match buried in the middle. Typing "tas" must return Toshkent, not Tasmania."""
    q = query.strip().lower()
    if not q:
        return []

    scored: list[tuple[int, Airport]] = []
    for airport in AIRPORTS.values():
        if airport.code.lower() == q:
            rank = 0
        elif airport.city.lower().startswith(q):
            rank = 1
        elif any(alias.startswith(q) for alias in airport.aliases):
            rank = 2
        elif q in airport.haystack:
            rank = 3
        else:
            continue
        scored.append((rank, airport))

    scored.sort(key=lambda pair: (pair[0], pair[1].city))
    return [airport for _, airport in scored[:limit]]
