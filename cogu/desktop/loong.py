import asyncio
import os
import sys
import threading
import time
import webbrowser
from pathlib import Path

import uvicorn

from cogu.app import create_app
from cogu.config.settings import Settings


APP_PORT = 8198
APP_HOST = "127.0.0.1"
APP_VERSION = "0.9.1"


class COGULoongDesktop:
    def __init__(self):
        self._loop = None

    async def _run_server(self):
        app = create_app(version=APP_VERSION)
        config = uvicorn.Config(
            app,
            host=APP_HOST,
            port=APP_PORT,
            log_level="warning",
            access_log=False,
        )
        server = uvicorn.Server(config)
        await server.serve()

    def _start_server(self):
        self._loop = asyncio.new_event_loop()
        asyncio.set_event_loop(self._loop)
        self._loop.run_until_complete(self._run_server())

    def start(self):
        thread = threading.Thread(target=self._start_server, daemon=True)
        thread.start()
        time.sleep(1.5)
        url = f"http://{APP_HOST}:{APP_PORT}/api/tools/dashboard"
        webbrowser.open(url)
        print(f"\n  COGU Loong v{APP_VERSION} Desktop")
        print(f"  Server running at http://{APP_HOST}:{APP_PORT}")
        print(f"  Dashboard at {url}")
        print(f"  Press Ctrl+C to stop\n")
        try:
            while True:
                time.sleep(1)
        except KeyboardInterrupt:
            print("\n  Shutting down...")
            sys.exit(0)


def main():
    if getattr(sys, "frozen", False):
        os.chdir(os.path.dirname(sys.executable))
    desktop = COGULoongDesktop()
    desktop.start()


if __name__ == "__main__":
    main()