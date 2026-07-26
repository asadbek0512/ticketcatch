import asyncio
import logging
import sys

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)s %(name)s: %(message)s",
    stream=sys.stderr,
)

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
