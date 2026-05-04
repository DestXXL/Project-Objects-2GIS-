from __future__ import annotations

import os
import socket
import threading
import time
import webbrowser

import uvicorn

from app.bootstrap import ensure_database_ready
from app.desktop_support import configure_desktop_environment


def _find_free_port() -> int:
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
        sock.bind(("127.0.0.1", 0))
        sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        return int(sock.getsockname()[1])


def _wait_for_server(host: str, port: int, timeout: float = 15.0) -> None:
    deadline = time.time() + timeout
    while time.time() < deadline:
        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
            sock.settimeout(0.5)
            if sock.connect_ex((host, port)) == 0:
                return
        time.sleep(0.1)
    raise RuntimeError("Локальный сервер не успел запуститься.")


def main() -> None:
    configure_desktop_environment()
    ensure_database_ready()

    host = "127.0.0.1"
    port = _find_free_port()
    url = f"http://{host}:{port}"

    config = uvicorn.Config(
        "app.main:app",
        host=host,
        port=port,
        reload=False,
        log_level="info",
    )
    server = uvicorn.Server(config)
    thread = threading.Thread(target=server.run, daemon=True)
    thread.start()

    _wait_for_server(host, port)
    print(f"Локальный web-интерфейс запущен: {url}")

    if os.environ.get("WASTE_REGISTRY_NO_BROWSER") != "1":
        webbrowser.open(url)

    try:
        while thread.is_alive():
            time.sleep(0.5)
    except KeyboardInterrupt:
        server.should_exit = True
        thread.join(timeout=5)


if __name__ == "__main__":
    main()
