"""
BACnet Explorer — GUI server + native desktop launcher.

The HTTP server and REST API run independently of how the UI is presented.
Two presentation modes:
  - launch_gui()  → opens the system browser (original behaviour)
  - launch_app()  → opens a native desktop window via pywebview (no browser needed)

When packaged with PyInstaller, launch_app() is the default entry point.
"""
from __future__ import annotations
import asyncio
import json
import sys
import threading
import traceback
import webbrowser
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import parse_qs, urlparse

from bacnet_explorer.session import Session
from bacnet_explorer.discovery import discover as bacnet_discover
from bacnet_explorer.browser import get_object_list, read_all_props
from bacnet_explorer.rw import read_prop, write_prop
from bacnet_explorer.utils import print_ok, print_info, print_warn, print_err

# When packaged with PyInstaller the real files live under sys._MEIPASS.
if getattr(sys, "frozen", False):
    STATIC_DIR = Path(sys._MEIPASS) / "bacnet_explorer" / "static"  # type: ignore[attr-defined]
else:
    STATIC_DIR = Path(__file__).parent / "static"


# ─── BACnet bridge ────────────────────────────────────────────────────────────

class BACnetBridge:
    """Owns the bacpypes3 event loop in a background thread."""

    def __init__(self, local_ip: str = "", bacnet_port: int = 47808) -> None:
        self.session = Session()
        self.loop = asyncio.new_event_loop()
        self._thread = threading.Thread(
            target=self.loop.run_forever, daemon=True, name="bacnet-loop"
        )
        self._thread.start()
        # Initialize the BACnet stack on the event loop thread.
        asyncio.run_coroutine_threadsafe(
            self._init(local_ip, bacnet_port), self.loop
        ).result(timeout=15)

    async def _init(self, local_ip: str, bacnet_port: int) -> None:
        self.session.start(local_ip=local_ip, port=bacnet_port)

    def run(self, coro, timeout: float = 15.0):
        """Submit a coroutine to the BACnet loop and return its result."""
        return asyncio.run_coroutine_threadsafe(coro, self.loop).result(timeout=timeout)

    def stop(self) -> None:
        self.session.stop()
        self.loop.call_soon_threadsafe(self.loop.stop)


# ─── HTTP handler ─────────────────────────────────────────────────────────────

class APIHandler(BaseHTTPRequestHandler):
    bridge: BACnetBridge  # injected by GUIServer

    def log_message(self, *_): pass  # silence access log

    # ── helpers ──

    def _json(self, data, status: int = 200) -> None:
        try:
            body = json.dumps(data, default=str).encode()
        except Exception as exc:
            print(f"  [GUI] JSON serialization error: {exc}", file=sys.stderr)
            body = json.dumps({"error": f"Serialization error: {exc}"}).encode()
        self.send_response(status)
        self.send_header("Content-Type", "application/json")
        self.send_header("Access-Control-Allow-Origin", "*")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def _file(self, path: Path, mime: str) -> None:
        data = path.read_bytes()
        self.send_response(200)
        self.send_header("Content-Type", mime)
        self.send_header("Content-Length", str(len(data)))
        self.end_headers()
        self.wfile.write(data)

    def _body(self) -> dict:
        n = int(self.headers.get("Content-Length", 0))
        return json.loads(self.rfile.read(n)) if n else {}

    def _qs(self) -> dict:
        return {k: v[0] for k, v in parse_qs(urlparse(self.path).query).items()}

    def _path(self) -> str:
        return urlparse(self.path).path

    def do_OPTIONS(self) -> None:
        self.send_response(204)
        self.send_header("Access-Control-Allow-Origin", "*")
        self.send_header("Access-Control-Allow-Methods", "GET, POST, OPTIONS")
        self.send_header("Access-Control-Allow-Headers", "Content-Type")
        self.end_headers()

    # ── GET ──

    def do_GET(self) -> None:
        try:
            self._handle_GET()
        except BaseException as exc:
            if isinstance(exc, (KeyboardInterrupt, SystemExit)):
                raise
            traceback.print_exc(file=sys.stderr)
            try:
                self._json({"error": f"{type(exc).__name__}: {exc}"}, 500)
            except Exception:
                pass

    def _handle_GET(self) -> None:
        p = self._path()

        if p in ("/", "/index.html"):
            self._file(STATIC_DIR / "index.html", "text/html; charset=utf-8")
            return

        if p == "/api/status":
            s = self.bridge.session
            self._json({
                "local_ip": s.local_ip,
                "device_count": len(s.devices),
                "active_id": s.active.device_id if s.active else None,
            })
            return

        if p == "/api/devices":
            devs = [
                {"id": d.device_id, "address": str(d.address),
                 "name": d.name, "vendor": d.vendor}
                for d in self.bridge.session.devices.values()
            ]
            self._json({"devices": devs})
            return

        if p == "/api/objects":
            qs = self._qs()
            device_id = int(qs.get("device_id", 0))
            s = self.bridge.session
            if device_id not in s.devices:
                self._json({"error": "Device not found"}, 404); return
            s.active = s.devices[device_id]
            try:
                obj_list = self.bridge.run(get_object_list(s), timeout=12)
                self._json({"objects": [
                    {"type": str(o[0]), "instance": int(o[1])} for o in obj_list
                ]})
            except Exception as exc:
                self._json({"error": str(exc)}, 500)
            return

        if p == "/api/props":
            qs = self._qs()
            device_id = int(qs.get("device_id", 0))
            obj_type  = qs.get("type", "")
            instance  = int(qs.get("instance", 0))
            s = self.bridge.session
            if device_id not in s.devices:
                self._json({"error": "Device not found"}, 404); return
            s.active = s.devices[device_id]
            try:
                props = self.bridge.run(read_all_props(s, obj_type, instance), timeout=20)
                self._json({"props": props})
            except Exception as exc:
                self._json({"error": str(exc)}, 500)
            return

        if p == "/api/read":
            qs = self._qs()
            device_id = int(qs.get("device_id", 0))
            obj_type  = qs.get("type", "")
            instance  = int(qs.get("instance", 0))
            prop      = qs.get("prop", "presentValue")
            s = self.bridge.session
            if device_id not in s.devices:
                self._json({"error": "Device not found"}, 404); return
            s.active = s.devices[device_id]
            try:
                val = self.bridge.run(read_prop(s, obj_type, instance, prop), timeout=10)
                self._json({"value": val})
            except Exception as exc:
                self._json({"error": str(exc)}, 500)
            return

        self.send_response(404); self.end_headers()

    # ── POST ──

    def do_POST(self) -> None:
        try:
            self._handle_POST()
        except BaseException as exc:
            if isinstance(exc, (KeyboardInterrupt, SystemExit)):
                raise
            traceback.print_exc(file=sys.stderr)
            try:
                self._json({"error": f"{type(exc).__name__}: {exc}"}, 500)
            except Exception:
                pass

    def _handle_POST(self) -> None:
        p = self._path()

        if p == "/api/discover":
            body   = self._body()
            low    = body.get("low")
            high   = body.get("high")
            target = body.get("target") or None  # e.g. "192.168.1.50:47808"
            try:
                devices = self.bridge.run(
                    bacnet_discover(self.bridge.session, low=low, high=high,
                                   timeout=5.0, address=target),
                    timeout=12,
                )
                self._json({"devices": [
                    {"id": d.device_id, "address": str(d.address),
                     "name": d.name, "vendor": d.vendor}
                    for d in devices
                ]})
            except Exception as exc:
                self._json({"error": str(exc)}, 500)
            return

        if p == "/api/write":
            body      = self._body()
            device_id = int(body.get("device_id", 0))
            obj_type  = body.get("type", "")
            instance  = int(body.get("instance", 0))
            prop      = body.get("prop", "presentValue")
            value     = str(body.get("value", ""))
            priority  = body.get("priority")
            if priority is not None:
                priority = int(priority)
            s = self.bridge.session
            if device_id not in s.devices:
                self._json({"error": "Device not found"}, 404); return
            s.active = s.devices[device_id]
            try:
                ok = self.bridge.run(
                    write_prop(s, obj_type, instance, prop, value, priority), timeout=10
                )
                self._json({"ok": ok})
            except Exception as exc:
                self._json({"error": str(exc)}, 500)
            return

        self.send_response(404); self.end_headers()


# ─── Server ───────────────────────────────────────────────────────────────────

class GUIServer:
    def __init__(
        self,
        local_ip: str = "",
        bacnet_port: int = 47808,
        web_port: int = 8080,
    ) -> None:
        self.web_port = web_port
        self.bridge = BACnetBridge(local_ip=local_ip, bacnet_port=bacnet_port)
        APIHandler.bridge = self.bridge
        self.httpd = ThreadingHTTPServer(("127.0.0.1", web_port), APIHandler)

    def run(self, open_browser: bool = True) -> None:
        url = f"http://127.0.0.1:{self.web_port}"
        print_ok(f"BACnet Explorer GUI → {url}")
        print_info("Press Ctrl+C to stop.")
        if open_browser:
            threading.Timer(0.6, lambda: webbrowser.open(url)).start()
        try:
            self.httpd.serve_forever()
        except KeyboardInterrupt:
            print()
        finally:
            self.httpd.shutdown()
            self.bridge.stop()
            print_info("GUI stopped.")


def launch_gui(
    local_ip: str = "",
    bacnet_port: int = 47808,
    web_port: int = 8080,
    open_browser: bool = True,
) -> None:
    GUIServer(local_ip=local_ip, bacnet_port=bacnet_port, web_port=web_port).run(open_browser)


def launch_app(
    local_ip: str = "",
    bacnet_port: int = 47808,
    web_port: int = 8080,
) -> None:
    """Launch BACnet Explorer as a native desktop window (no external browser).

    Uses pywebview to render the UI inside a standalone application window.
    Falls back to the system browser when pywebview is not installed.
    """
    try:
        import webview  # type: ignore[import-untyped]
    except ImportError:
        print_warn("pywebview not installed — falling back to browser mode.")
        print_warn("For the native window run: pip install pywebview")
        launch_gui(local_ip=local_ip, bacnet_port=bacnet_port, web_port=web_port, open_browser=True)
        return

    server = GUIServer(local_ip=local_ip, bacnet_port=bacnet_port, web_port=web_port)

    # Run the HTTP server in a background thread so webview.start() can block.
    threading.Thread(
        target=server.httpd.serve_forever, daemon=True, name="http-server"
    ).start()

    url = f"http://127.0.0.1:{web_port}"
    print_ok(f"BACnet Explorer  {url}")
    print_info("Opening desktop window…")

    try:
        webview.create_window(
            "BACnet Explorer",
            url,
            width=1280,
            height=820,
            min_size=(900, 560),
            text_select=True,
        )
        webview.start()
    finally:
        server.httpd.shutdown()
        server.bridge.stop()
        print_info("BACnet Explorer closed.")
