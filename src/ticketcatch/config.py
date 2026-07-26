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
    currency: str = "usd"
    # Point of sale: airfares differ by the country you buy from, so this is where the traveller
    # buys (Korea), not where the server runs.
    market: str = "kr"
    poll_interval_seconds: int = 28800  # 8h — three times a day
    top_n: int = 3  # how many cheapest options to show per watch
    dry_run: bool = True  # True = log the digest, never send to Telegram


settings = Settings()
