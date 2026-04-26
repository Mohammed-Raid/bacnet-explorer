# BACnet Explorer

A fully-featured BACnet/IP client for Windows — discover, browse, read, write, and subscribe to BACnet devices and objects on your network.

Inspired by YABE (Yet Another BACnet Explorer).

---

## Download

Grab the latest **Windows build** from the [Releases](../../releases) page:

```
BACnet-Explorer-windows-x64.zip
```

Unzip and double-click **`BACnet Explorer.exe`** inside the folder — no Python needed.

---

## Features

| Feature | CLI | GUI |
|---------|-----|-----|
| Discover all devices (WhoIs broadcast) | ✓ | ✓ |
| Discover by device ID range | ✓ | ✓ |
| Direct unicast discover (same-machine) | ✓ | ✓ |
| Browse object list | ✓ | ✓ |
| Read all properties | ✓ | ✓ |
| Read single property | ✓ | ✓ |
| Write property (with priority) | ✓ | ✓ |
| Subscribe COV (Change of Value) | ✓ | — |
| Read TrendLog (ReadRange) | ✓ | — |

---

## Run from source

**Requirements:** Python 3.12+

```bash
pip install bacpypes3 ifaddr colorama
python -m bacnet_explorer          # interactive menu
python -m bacnet_explorer gui --browser   # open in system browser
```

**With native desktop window (pywebview):**

```bash
# Python 3.12 / 3.13
pip install ".[app]"

# Python 3.14+ — pythonnet 3.1+ is required (pre-release)
pip install --pre ".[app]"

python -m bacnet_explorer gui
```

> **Note for Python 3.14+:** The Windows native window backend (pywebview) requires
> `pythonnet >= 3.1.0rc0` because earlier versions do not have an ABI mapping for
> Python 3.14. Use `pip install --pre ".[app]"` to get the pre-release.

---

## CLI reference

```
python -m bacnet_explorer [--ip IP/MASK] [--port PORT] <command>

Commands:
  discover [--range lo:hi]
  browse   <device_id>
  read     <device_id> <type> <inst> <prop>
  write    <device_id> <type> <inst> <prop> <value> [--priority N]
  props    <device_id> <type> <inst>
  cov      <device_id> <type> <inst> [--lifetime N]
  readrange <device_id> <inst> [--count N]
  gui      [--browser] [--web-port PORT]
```

**Tip — BACnet server on the same machine:**  
Windows does not loop back UDP broadcasts to the same host. Use the GUI's
**"Direct IP"** button (or `--range` with a unicast address) to reach a
local server.

---

## Build the .exe yourself

```bash
pip install --pre ".[app]" pyinstaller
pyinstaller bacnet_explorer.spec --clean -y
# Output: dist/BACnet Explorer/BACnet Explorer.exe
```

GitHub Actions builds a Windows binary automatically on every tagged release.

---

## Stack

- [bacpypes3](https://github.com/JoelBender/BACpypes3) — BACnet/IP stack
- [pywebview](https://pywebview.flowrl.com/) — native OS webview window
- [colorama](https://github.com/tartley/colorama) — Windows ANSI colours
- [ifaddr](https://github.com/pydron/ifaddr) — network interface enumeration
- [PyInstaller](https://pyinstaller.org/) — standalone .exe packaging

---

## License

MIT
