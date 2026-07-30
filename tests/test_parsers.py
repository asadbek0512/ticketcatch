"""Parser tests.

These exist because the failure mode that matters here is silent: Trip.com re-hashes its CSS on
every build, so a redesign doesn't raise — it just quietly starts reporting "직항" as one stop and
nobody notices until a user compares the digest with their own browser. Each case below is a real
string one of the sources returned.
"""

from datetime import date, datetime, timedelta

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


# --- round trip --------------------------------------------------------------------------------


def test_round_trip_is_never_cached_as_the_one_way():
    """A return fare is priced as a pair, so it is a different number from the same outbound flown
    one way. Sharing a cache key would serve one as the other."""
    from ticketcatch.search import cache_key

    opts = SearchOpts.of("krw", "kr")
    one_way = cache_key("ICN", "TAS", date(2026, 9, 2), opts)
    there_back = cache_key("ICN", "TAS", date(2026, 9, 2), opts, ret=date(2026, 9, 16))
    assert one_way != there_back
    assert there_back.endswith("|r2026-09-16")


def test_route_key_separates_the_trip_types():
    from ticketcatch.models import route_key

    assert route_key("ICN", "TAS", date(2026, 9, 2)) == "ICN-TAS-2026-09-02"
    assert route_key("ICN", "TAS", date(2026, 9, 2), date(2026, 9, 16)) == (
        "ICN-TAS-2026-09-02-r2026-09-16"
    )


def test_dedupe_keeps_trips_that_differ_only_in_the_way_back():
    """Same outbound, two different returns — collapsing them would hide the cheaper pairing."""
    early = Quote(
        source="kiwi",
        price=990_000,
        currency="krw",
        depart_at="2026-09-02 08:35",
        stops=1,
        return_at="2026-09-16 22:30",
    )
    late = Quote(
        source="kiwi",
        price=1_050_000,
        currency="krw",
        depart_at="2026-09-02 08:35",
        stops=1,
        return_at="2026-09-17 22:30",
    )
    assert len(dedupe([early, late])) == 2
    # ...but the same pairing quoted twice still collapses to the cheaper quote.
    cheaper = Quote(**{**early.__dict__, "source": "tripcom", "price": 940_000})
    merged = dedupe([early, cheaper])
    assert len(merged) == 1 and merged[0].price == 940_000


def test_return_before_departure_is_rejected():
    """The panel must not be able to hold an impossible trip."""
    from ticketcatch.bot import _apply
    from ticketcatch.models import Preference

    pref = Preference(user_id="1", depart_date=date.today() + timedelta(days=30))
    assert _apply(pref, "ret", (pref.depart_date - timedelta(days=1)).isoformat()) == (
        "err_return_before"
    )
    assert _apply(pref, "ret", pref.depart_date.isoformat()) == "err_return_before"
    assert _apply(pref, "ret", (pref.depart_date + timedelta(days=7)).isoformat()) is None
    assert pref.return_date == pref.depart_date + timedelta(days=7)
    # empty value = the "remove return" button
    assert _apply(pref, "ret", "") is None
    assert pref.return_date is None


def test_moving_departure_past_the_return_drops_the_return():
    from ticketcatch.bot import _apply
    from ticketcatch.models import Preference

    pref = Preference(user_id="1", depart_date=date.today() + timedelta(days=10))
    _apply(pref, "ret", (date.today() + timedelta(days=17)).isoformat())
    assert pref.return_date is not None
    _apply(pref, "depart", (date.today() + timedelta(days=40)).isoformat())
    assert pref.return_date is None  # not silently left before the new departure


# --- price history ------------------------------------------------------------------------------


def _points(prices: list[int]) -> list[tuple[datetime, int]]:
    start = datetime(2026, 7, 1, 6, 0)
    return [(start + timedelta(hours=8 * i), p) for i, p in enumerate(prices)]


def test_sparkline_scales_to_the_window_not_to_absolute_money():
    from ticketcatch.history import sparkline

    # Same shape, hundredfold prices: the bars must read the same, because the question is
    # "high or low for this route", not "expensive in general".
    assert sparkline([100, 200, 300]) == sparkline([10_000, 20_000, 30_000])
    assert sparkline([500, 500, 500]) == "▁▁▁"  # flat, not noise
    assert sparkline([]) == ""
    assert len(sparkline(list(range(200)))) <= 24  # still one phone line


def test_verdict_says_buy_at_the_bottom_and_wait_at_the_top():
    from ticketcatch.history import verdict

    assert "🟢" in verdict([900, 800, 700], "uz")  # cheapest right now
    assert "🔴" in verdict([700, 800, 900], "uz")  # dearest right now
    assert "🟡" in verdict([700, 1000, 850], "uz")  # in between
    assert "➖" in verdict([1000, 1005, 1000], "uz")  # no real movement


def test_history_needs_two_captures_before_it_claims_a_trend():
    from ticketcatch.history import format_history

    one = format_history(_points([500_000]), "krw", "uz", "ICN → TAS", "2026-09-01")
    assert "▁" not in one and "█" not in one  # a single price is not a graph
    two = format_history(_points([500_000, 400_000]), "krw", "uz", "ICN → TAS", "2026-09-01")
    assert "█" in two or "▁" in two


def test_threshold_suggestions_come_from_the_observed_price():
    from ticketcatch.history import suggestions

    assert suggestions([]) == []
    offered = suggestions(_points([1_000_000, 900_000]))
    assert offered  # derived from 900_000, the cheapest seen — not fixed round numbers
    assert all(0 < price < 900_000 for price in offered)
    assert offered == sorted(offered, reverse=True)


def test_paused_watches_are_kept_but_not_polled():
    from ticketcatch.models import Watch

    fresh = Watch(user_id="1", depart_date=date.today() + timedelta(days=10))
    assert fresh.active and not fresh.paused  # pausing is opt-in, and separate from deleting


# --- stored prices, shown instantly -------------------------------------------------------------


def test_ago_label_speaks_in_the_unit_a_person_thinks_in():
    from ticketcatch.i18n import ago_label

    assert ago_label(5, "uz") == "hozir"  # "1 daqiqa oldin" would be noise
    assert "12" in ago_label(12 * 60, "uz")
    assert ago_label(3 * 3600, "en") == "3h ago"
    assert ago_label(2 * 86400, "en") == "2d ago"
    assert ago_label(-5, "uz") == "hozir"  # a clock skew must not read "-1 kun oldin"


def test_watch_card_shows_the_stored_prices_and_how_old_they_are():
    from datetime import timezone

    from ticketcatch.bot import _watch_card
    from ticketcatch.models import PriceQuote, Watch, utcnow

    watch = Watch(user_id="1", depart_date=date.today() + timedelta(days=20), currency="krw")
    captured = utcnow() - timedelta(hours=3)
    board = [
        PriceQuote(route_key="r", price=500_000, currency="krw", airline="Asiana Airlines",
                   depart_at="2026-09-01 10:00", stops=0, captured_at=captured),
        PriceQuote(route_key="r", price=610_000, currency="krw", airline="China Southern",
                   depart_at="2026-09-01 22:50", stops=1, captured_at=captured),
    ]
    card = _watch_card(watch, "uz", board)
    assert "500,000 KRW" in card and "610,000 KRW" in card
    assert "3 soat oldin" in card  # a price without its age is a claim, not an observation
    assert "kuniga 2 marta" in card  # said once, on the status line — not repeated

    # No captures yet: say so and point at the live search, rather than showing an empty board.
    empty = _watch_card(watch, "uz", [])
    assert "🔍" in empty and "tekshirilgan" not in empty


def test_naive_timestamps_from_sqlite_do_not_break_the_age():
    from datetime import datetime as dt

    from ticketcatch.bot import _ago

    # SQLite hands back naive datetimes even though we write aware ones; subtracting the two
    # shapes raises unless _ago normalises first.
    assert _ago(dt.utcnow() - timedelta(hours=2), "en") == "2h ago"


def test_a_translation_may_contain_a_lang_placeholder():
    from ticketcatch.i18n import t
    from ticketcatch.menu import settings_text
    from ticketcatch.models import Preference

    # "🌐 Til: {lang}" — the settings screen names the language, so the kwarg is called lang.
    # Before t()'s parameters were positional-only this raised TypeError and killed /sozlama.
    assert t("uz", "settings_title", lang="O'zbek", currency="KRW", market="Koreya")

    for code in ("uz", "ru", "en"):
        text = settings_text(Preference(user_id="1", lang=code))
        assert "{lang}" not in text and "{currency}" not in text and "{market}" not in text


def test_changing_language_changes_the_next_digest():
    from ticketcatch.models import PriceQuote, Watch
    from ticketcatch.notifier import format_digest

    # The watch was created in Uzbek; the user has since switched to Russian.
    watch = Watch(user_id="1", depart_date=date.today() + timedelta(days=10), lang="uz")
    board = [PriceQuote(route_key="r", price=500_000, currency="krw", airline="Asiana")]

    # With no override the watch's own language is still the fallback.
    assert format_digest(watch, board, None) == format_digest(watch, board, None, lang="uz")
    assert format_digest(watch, board, None, lang="ru") != format_digest(watch, board, None)
    assert format_digest(watch, board, None, lang="ru") == format_digest(
        Watch(user_id="1", depart_date=watch.depart_date, lang="ru"), board, None
    )


# --- delivery schedule --------------------------------------------------------------------------


def _utc(hour: int):
    from datetime import datetime as dt
    from datetime import timezone as tz

    return dt(2026, 8, 1, hour, 0, tzinfo=tz.utc)


def test_the_evening_slot_is_the_morning_one_twelve_hours_later():
    from ticketcatch import schedule

    assert schedule.slots(9) == (9, 21)
    assert schedule.slots(21) == (21, 9)  # wraps past midnight
    assert schedule.slot_label(9) == "09:00 · 21:00"


def test_a_brand_new_watch_does_not_wait_for_its_slot():
    from ticketcatch import schedule

    assert schedule.is_due(_utc(3), "Asia/Seoul", 9, last_sent_at=None)


def test_a_watch_is_served_at_the_users_local_hour_not_ours():
    from ticketcatch import schedule

    yesterday = _utc(0) - timedelta(hours=20)
    # 00:00 UTC is 09:00 in Seoul and 05:00 in Tashkent: the same tick is due for one, not the other.
    assert schedule.is_due(_utc(0), "Asia/Seoul", 9, yesterday)
    assert not schedule.is_due(_utc(0), "Asia/Tashkent", 9, yesterday)


def test_the_same_slot_is_not_served_twice():
    from ticketcatch import schedule

    just_sent = _utc(0) - timedelta(minutes=30)  # an earlier tick of the same hour
    assert not schedule.is_due(_utc(0), "Asia/Seoul", 9, just_sent)


def test_an_unknown_zone_costs_accuracy_not_a_crash():
    from ticketcatch import schedule

    assert schedule.local_time(_utc(7), "Mars/Olympus").hour == 7  # falls back to UTC


def test_a_new_user_starts_in_the_default_language():
    """Not in whatever language their Telegram client is set to — a Russian-language phone in
    Tashkent is common, and guessing from it greeted people in a language they never chose."""
    import inspect

    from ticketcatch.db import get_preference
    from ticketcatch.models import Preference
    from ticketcatch.config import settings

    assert "lang_hint" not in inspect.signature(get_preference).parameters
    assert Preference(user_id="new").lang == settings.default_lang
