"""Parser tests.

These exist because the failure mode that matters here is silent: Trip.com re-hashes its CSS on
every build, so a redesign doesn't raise — it just quietly starts reporting "직항" as one stop and
nobody notices until a user compares the digest with their own browser. Each case below is a real
string one of the sources returned.
"""

from datetime import date, timedelta

import pytest

from ticketcatch import airports, money
from ticketcatch.i18n import LANGS, UZ, day_label, normalize, t
from ticketcatch.search import dedupe
from ticketcatch.sources import Quote, SearchOpts
from ticketcatch.sources import tripcom


# --- Trip.com: bilingual board -----------------------------------------------------------------


@pytest.mark.parametrize(
    "raw,expected",
    [
        ("Nonstop", 0),
        ("직항", 0),
        ("Direct", 0),
        ("2 stops in Beijing, Urumqi", 2),
        ("2회 경유", 2),
        ("1 stop in Almaty", 1),
        ("6h 40m in Beijing", 1),  # a layover duration, not a count — must not read as 6 stops
        ("베이징 경유", 1),
        ("", None),
    ],
)
def test_tripcom_stops(raw, expected):
    assert tripcom._stops(raw) == expected


@pytest.mark.parametrize(
    "raw,expected",
    [
        ("7h 40m", 460),
        ("7시간 40분", 460),
        ("12h", 720),
        ("45m", 45),
        ("", None),
        ("--", None),
    ],
)
def test_tripcom_duration(raw, expected):
    assert tripcom._duration(raw) == expected


def test_tripcom_stamp_trims_seconds():
    assert tripcom._stamp("2026-08-15 16:35:00") == "2026-08-15 16:35"
    assert tripcom._stamp(None) == ""


# --- dedupe ------------------------------------------------------------------------------------


def _q(source: str, price: int, depart="2026-08-15 16:35", stops=0) -> Quote:
    return Quote(source=source, price=price, currency="krw", depart_at=depart, stops=stops)


def test_dedupe_keeps_cheapest_of_the_same_flight():
    merged = dedupe([_q("kiwi", 600_000), _q("tripcom", 543_600), _q("google", 580_000)])
    assert len(merged) == 1
    assert merged[0].price == 543_600
    assert merged[0].source == "tripcom"


def test_dedupe_separates_flights_and_sorts_by_price():
    merged = dedupe(
        [
            _q("kiwi", 700_000, depart="2026-08-15 22:10"),
            _q("kiwi", 543_600),
            _q("kiwi", 620_000, stops=1),  # same minute, different routing = different offer
        ]
    )
    assert [o.price for o in merged] == [543_600, 620_000, 700_000]


def test_dedupe_falls_back_to_flight_number_without_a_timestamp():
    a = Quote(source="kiwi", price=500_000, currency="krw", flight_number="OZ573")
    b = Quote(source="google", price=480_000, currency="krw", flight_number="OZ573")
    assert [o.price for o in dedupe([a, b])] == [480_000]


# --- money -------------------------------------------------------------------------------------


def test_format_price_groups_only_where_it_reads_naturally():
    assert money.format_price(543_600, "krw") == "543,600 KRW"
    assert money.format_price(382, "usd") == "382 USD"


def test_market_carries_its_own_currency():
    assert money.currency_for("uz") == "uzs"
    assert money.currency_for("kr") == "krw"
    assert money.currency_for("zz") == "usd"  # unknown market still yields something spendable


def test_search_opts_normalizes_case():
    opts = SearchOpts.of(currency="KRW", market="KR")
    assert opts.currency == "krw" and opts.market == "kr"
    assert opts.key == "krw@kr"


# --- airports ----------------------------------------------------------------------------------


def test_search_ranks_the_obvious_answer_first():
    assert airports.search("tas")[0].code == "TAS"
    assert airports.search("dubay")[0].code == "DXB"
    assert airports.search("tashkent")[0].code == "TAS"  # alias spelling
    assert airports.search("seul")[0].code in {"ICN", "GMP"}


def test_search_is_empty_for_nonsense():
    assert airports.search("qqqqzz") == []
    assert airports.search("") == []


def test_unknown_code_still_looks_like_iata():
    assert airports.is_iata("DAC") and airports.get("DAC") is None
    assert not airports.is_iata("DACC")
    assert airports.city("DAC") == "DAC"  # unlisted codes degrade to themselves, never crash


def test_every_popular_and_region_code_resolves():
    for code in airports.POPULAR:
        assert airports.get(code) is not None, code
    for region in airports.REGIONS:
        assert airports.in_region(region), region


# --- i18n --------------------------------------------------------------------------------------


def test_translations_cover_every_key():
    """Uzbek is the reference; a key added there must be added everywhere or it silently falls back."""
    for code, table in LANGS.items():
        missing = set(UZ) - set(table)
        assert not missing, f"{code} is missing: {sorted(missing)}"


def test_translations_share_their_placeholders():
    import re

    fields = lambda text: set(re.findall(r"{(\w+)}", text))  # noqa: E731
    for code, table in LANGS.items():
        for key, text in table.items():
            assert fields(text) == fields(UZ[key]), f"{code}.{key} placeholders differ"


def test_unknown_language_falls_back_instead_of_showing_a_key():
    assert normalize("de-DE") == "uz"
    assert t("de", "btn_search") == UZ["btn_search"]
    assert t("en", "nope_not_a_key") == "nope_not_a_key"


def test_day_label_is_localized():
    day = date(2026, 8, 15)
    assert "avg" in day_label(day, "uz")
    assert "авг" in day_label(day, "ru")
    assert "Aug" in day_label(day, "en")


# --- calendar ----------------------------------------------------------------------------------


def test_calendar_never_starts_in_the_past():
    from ticketcatch.search import calendar_days

    days = calendar_days(date.today())
    assert days[0] >= date.today() + timedelta(days=1)
    assert len(days) == 8


# --- airline naming ----------------------------------------------------------------------------


def test_codes_become_names_only_when_they_are_codes():
    """Sources run concurrently now, so Trip.com can finish before the directory that names its
    carriers is filled — the resolution has to survive being applied to already-named quotes."""
    from ticketcatch.search import _named
    from ticketcatch.sources import AIRLINE_NAMES

    AIRLINE_NAMES["OZ"] = "Asiana Airlines"
    AIRLINE_NAMES["HY"] = "Uzbekistan Airways"

    assert _named(Quote(source="tripcom", price=1, currency="krw", airline="OZ")).airline == (
        "Asiana Airlines"
    )
    assert _named(Quote(source="tripcom", price=1, currency="krw", airline="OZ, HY")).airline == (
        "Asiana Airlines, Uzbekistan Airways"
    )
    # already a name: must pass through untouched, not get uppercased into "ASIANA AIRLINES"
    assert _named(Quote(source="kiwi", price=1, currency="krw", airline="Asiana Airlines")).airline == (
        "Asiana Airlines"
    )
    # unknown code stays readable rather than becoming empty
    assert _named(Quote(source="tripcom", price=1, currency="krw", airline="ZZ")).airline == "ZZ"
    assert _named(Quote(source="tripcom", price=1, currency="krw", airline="")).airline == ""
