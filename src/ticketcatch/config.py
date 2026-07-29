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
    poll_interval_seconds: int = 43200  # 12h — twice a day
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
