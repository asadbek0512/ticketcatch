import asyncio
import logging
import sys

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)s %(name)s: %(message)s",
    stream=sys.stderr,
)

# These log every request URL at INFO, and our source URLs carry the Travelpayouts token as a
# query parameter — at INFO the API key ends up in plain text in the pm2 log file. Warnings and
# errors still come through, which is all we ever read them for.
for _noisy in ("httpx", "httpcore", "primp"):
    logging.getLogger(_noisy).setLevel(logging.WARNING)

_USAGE = "usage: python -m ticketcatch [bot | poll | loop]"


def main() -> None:
    cmd = sys.argv[1] if len(sys.argv) > 1 else ""

    if cmd == "bot":
        from .bot import run_bot

        asyncio.run(run_bot())
    elif cmd == "poll":
        from .poller import poll_once

        asyncio.run(poll_once())
    elif cmd == "loop":
        from .poller import loop

        asyncio.run(loop())
    else:
        print(_USAGE, file=sys.stderr)
        sys.exit(1)


if __name__ == "__main__":
    main()
