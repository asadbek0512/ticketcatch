"""Currencies and points of sale.

Two settings that look like one but aren't: **market** is the country the ticket is bought from,
which changes the fare itself, and **currency** is the money it's quoted in, which only changes
how the same fare is written. Picking a country therefore also picks a sensible currency, but a
user in Korea who thinks in dollars can still keep USD.
"""

from dataclasses import dataclass

from .i18n import country

# Currencies whose amounts are conventionally written in thousands groups (₩543,600). Sub-unit
# currencies get their decimals from the source and are shown as-is.
GROUPED = {"krw", "uzs", "kzt", "jpy", "rub", "vnd", "idr"}


@dataclass(frozen=True)
class Market:
    code: str
    flag: str
    currency: str

    def name(self, lang: str) -> str:
        return country(self.code, lang)


# Offered in the menu, most likely first. The full list of markets our sources accept is much
# longer; these are the ones this bot's users actually buy from.
MARKETS: tuple[Market, ...] = (
    Market("kr", "🇰🇷", "krw"),
    Market("uz", "🇺🇿", "uzs"),
    Market("us", "🇺🇸", "usd"),
    Market("ru", "🇷🇺", "rub"),
    Market("kz", "🇰🇿", "kzt"),
    Market("tr", "🇹🇷", "try"),
    Market("ae", "🇦🇪", "aed"),
    Market("de", "🇩🇪", "eur"),
    Market("gb", "🇬🇧", "gbp"),
    Market("jp", "🇯🇵", "jpy"),
)

CURRENCIES: tuple[tuple[str, str], ...] = (
    ("krw", "₩ KRW"),
    ("usd", "$ USD"),
    ("uzs", "so'm UZS"),
    ("rub", "₽ RUB"),
    ("eur", "€ EUR"),
    ("kzt", "₸ KZT"),
    ("try", "₺ TRY"),
    ("jpy", "¥ JPY"),
    ("aed", "AED"),
    ("gbp", "£ GBP"),
)

_BY_CODE = {m.code: m for m in MARKETS}
_CURRENCY_LABELS = dict(CURRENCIES)


def market(code: str) -> Market | None:
    return _BY_CODE.get(code.lower())


def market_label(code: str, lang: str) -> str:
    found = market(code)
    return f"{found.flag} {found.name(lang)}" if found else code.upper()


def currency_label(code: str) -> str:
    return _CURRENCY_LABELS.get(code.lower(), code.upper())


def currency_for(market_code: str) -> str:
    """The money people quote prices in when buying from that country."""
    found = market(market_code)
    return found.currency if found else "usd"


def format_price(amount: int, currency: str) -> str:
    """'543600' + 'krw' -> '543,600 KRW'. Grouping only where it reads naturally."""
    code = currency.lower()
    body = f"{amount:,}" if code in GROUPED else str(amount)
    return f"{body} {currency.upper()}"
