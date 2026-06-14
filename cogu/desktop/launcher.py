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
from cogu.core.runner import Runner


APP_PORT = 8198
APP_HOST = "127.0.0.1"


class COGULauncher:
    def __init__(self):
        self._server_task = None
        self._loop = None
        self._settings = Settings.default()

    async def _run_server(self):
        app = create_app(version="0.9.1")
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
        url = f"http://{APP_HOST}:{APP_PORT}/dashboard"
        webbrowser.open(url)
        print(f"\n  COGU AGENT v0.9.1 Desktop")
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
    sys.path.insert(0, str(Path(__file__).resolve().parent.parent.parent))
    launcher = COGULauncher()
    launcher.start()


if __name__ == "__main__":
    main()
