from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    # --- Telegram ---
    telegram_bot_token: str = ""
    telegram_owner_id: str = ""  # private chat that receives error/admin messages

    # --- Data sources ---
    # Travelpayouts (Aviasales Data API) token — free, also pays affiliate commission.
    # Get it at https://www.travelpayouts.com -> Tools -> API tokens.
    travelpayouts_token: str = ""
    travelpayouts_marker: str = ""  # affiliate marker appended to deep links (optional)

    # Duffel flight offers API — returns the full airline-by-airline schedule, not a single
    # cached price. Test-mode token is free at app.duffel.com -> Developers -> Access tokens.
    duffel_token: str = ""

    # --- Runtime ---
    db_path: str = "data/ticketcatch.sqlite"
    # Fallback currency/market for users who haven't chosen: airfares differ by the country you
    # buy from, so this is where the traveller buys, not where the server runs. Per-user values
    # live on Preference and Watch; these only seed a brand-new user.
    currency: str = "krw"
    market: str = "kr"
    default_lang: str = "uz"
    # How often the poller wakes to ask "is anyone due?". Not how often anyone is priced: each
    # watch is still checked twice a day, at the hour its owner picked in Settings.
    poll_tick_seconds: int = 900  # 15min
    # A watch with a target price is also checked between digests, so "under 400,000" arrives when
    # it happens rather than the next morning. Only the fast JSON source is asked, so this costs one
    # HTTP request per route — running the browser sources this often would not be affordable.
    alert_scan_seconds: int = 3600  # 1h
    # Where genuinely good fares are announced publicly: a channel id like "@ticketcatch_deals" or
    # "-1001234567890". Empty means the bot has no public face and posts nothing.
    deals_channel_id: str = ""
    # How far under a route's usual price a fare must be before it is worth a stranger's attention.
    deal_discount_percent: int = 15
    deal_repeat_hours: int = 24  # don't announce the same route again inside this window
    top_n: int = 3  # how many cheapest options to show per watch
    dry_run: bool = True  # True = log the digest, never send to Telegram

    # --- Capacity ---
    # A browser-backed source costs ~350MB and ~90s per search, so these caps are what keeps the
    # box alive once more than a handful of people use the bot at once.
    browser_concurrency: int = 3  # simultaneous browser pages across the whole process
    route_concurrency: int = 4  # routes the poller works on in parallel
    cache_ttl_seconds: int = 1800  # 30min — repeat searches of a route+day are served from cache
    search_cooldown_seconds: int = 60  # per-user floor between on-demand searches


settings = Settings()
