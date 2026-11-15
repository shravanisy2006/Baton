"""Run the background job workers as their own process (optional).

By default the API process runs the workers itself. On a plan with a separate worker service, set
BATON_RUN_WORKER=0 on the API and start this with:  python -m app.worker
"""

import logging
import signal

from .config import get_settings
from .db import init_db
from .jobs import _stop, recover_interrupted, start_workers, stop_workers

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s: %(message)s")


def main() -> None:
    get_settings().check()
    init_db()
    recover_interrupted()
    start_workers()
    signal.signal(signal.SIGTERM, lambda *_: _stop.set())
    try:
        while not _stop.wait(1):
            pass
    except KeyboardInterrupt:
        pass
    stop_workers()


if __name__ == "__main__":
    main()
