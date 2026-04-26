"""
BACnet Explorer — entry point.

Usage:
  python -m bacnet_explorer                                   # interactive menu
  python -m bacnet_explorer discover [--range lo:hi]
  python -m bacnet_explorer browse <device_id>
  python -m bacnet_explorer read <device_id> <type> <inst> <prop>
  python -m bacnet_explorer write <device_id> <type> <inst> <prop> <value> [--priority N]
  python -m bacnet_explorer props <device_id> <type> <inst>
  python -m bacnet_explorer cov <device_id> <type> <inst> [--lifetime N]
  python -m bacnet_explorer readrange <device_id> <inst> [--count N]

Global options:
  --ip IP/MASK    local BACnet/IP address (default: auto-detect)
  --port PORT     local UDP port (default: 47808; use 47809 when server is on same machine)
"""

from __future__ import annotations
import argparse
import asyncio
import sys

from bacnet_explorer.session import Session, DeviceInfo
from bacnet_explorer.discovery import discover
from bacnet_explorer.browser import get_object_list, read_all_props
from bacnet_explorer.rw import read_prop, write_prop, read_range
from bacnet_explorer.cov import subscribe_cov
from bacnet_explorer.gui import launch_gui, launch_app
from bacnet_explorer.utils import (
    print_ok, print_err, print_info, print_warn,
    print_table, print_banner,
    ask, ask_int,
    Y, C, G, D, RS,
)


# ─── Display helpers ──────────────────────────────────────────────────────────

def _device_table(devices: list[DeviceInfo]) -> None:
    rows = [[str(d.device_id), str(d.address), d.name, d.vendor] for d in devices]
    print_table(["ID", "Address", "Name", "Vendor"], rows)


def _object_table(obj_list: list) -> None:
    rows = [[str(o[0]), str(o[1])] for o in obj_list]
    print_table(["Object Type", "Instance"], rows)


def _props_table(props: dict) -> None:
    rows = [[k, str(v)] for k, v in props.items()]
    print_table(["Property", "Value"], rows)


# ─── Require active device guard ─────────────────────────────────────────────

def _need_device(session: Session) -> bool:
    if session.active is None:
        print_warn("No active device. Run Discover first (option 1 or 2).")
        return False
    return True


def _resolve_device(session: Session, device_id: int) -> bool:
    if device_id not in session.devices:
        print_warn(f"Device {device_id} not in discovered list. Run discover first.")
        return False
    session.active = session.devices[device_id]
    return True


# ─── CLI command handlers ─────────────────────────────────────────────────────

async def cmd_discover(session: Session, args) -> None:
    low = high = None
    if args.range:
        try:
            low, high = map(int, args.range.split(":"))
        except ValueError:
            print_err("--range must be lo:hi (e.g. 100:200)")
            return
    devices = await discover(session, low=low, high=high, timeout=5.0)
    if devices:
        print_ok(f"Found {len(devices)} device(s):")
        _device_table(devices)


async def cmd_browse(session: Session, args) -> None:
    if not _resolve_device(session, args.device_id):
        return
    obj_list = await get_object_list(session)
    if obj_list:
        print_ok(f"Device {args.device_id} — {len(obj_list)} object(s):")
        _object_table(obj_list)


async def cmd_read(session: Session, args) -> None:
    if not _resolve_device(session, args.device_id):
        return
    val = await read_prop(session, args.obj_type, args.instance, args.prop)
    if val is not None:
        print_ok(f"({args.obj_type},{args.instance}).{args.prop} = {val}")


async def cmd_write(session: Session, args) -> None:
    if not _resolve_device(session, args.device_id):
        return
    ok = await write_prop(session, args.obj_type, args.instance,
                          args.prop, args.value, args.priority)
    if ok:
        print_ok(f"Wrote {args.value!r} → ({args.obj_type},{args.instance}).{args.prop}")


async def cmd_props(session: Session, args) -> None:
    if not _resolve_device(session, args.device_id):
        return
    props = await read_all_props(session, args.obj_type, args.instance)
    if props:
        print_ok(f"({args.obj_type},{args.instance}) — {len(props)} properties:")
        _props_table(props)


async def cmd_cov(session: Session, args) -> None:
    if not _resolve_device(session, args.device_id):
        return
    await subscribe_cov(session, args.obj_type, args.instance, args.lifetime)


async def cmd_readrange(session: Session, args) -> None:
    if not _resolve_device(session, args.device_id):
        return
    records = await read_range(session, args.instance, getattr(args, "count", 20))
    if records:
        print_ok(f"TrendLog {args.instance} — {len(records)} record(s):")
        for i, rec in enumerate(records):
            print(f"  {D}{i + 1:>4}{RS}  {rec}")
    else:
        print_info("No records returned.")


# ─── Interactive menu ─────────────────────────────────────────────────────────

MENU = [
    ("Discovery",    None),
    ("Discover All Devices",    "discover_all"),
    ("Discover Range",          "discover_range"),
    ("Select Active Device",    "select"),
    ("Browse",       None),
    ("Browse Objects",          "browse"),
    ("Read All Properties",     "props"),
    ("Read / Write", None),
    ("Read Property",           "read"),
    ("Write Property",          "write"),
    ("Live",         None),
    ("Subscribe COV",           "cov"),
    ("Read TrendLog",           "readrange"),
]


async def run_interactive_menu(session: Session) -> None:
    numbered = [(label, action) for label, action in MENU if action is not None]

    while True:
        print_banner(session)

        n = 1
        for label, action in MENU:
            if action is None:
                if label:
                    print(f"  {D}{label}{RS}")
            else:
                print(f"  {C}{n}{RS} {D}›{RS} {label}")
                n += 1
        print(f"\n  {D}0 › Quit{RS}\n")

        try:
            raw = input(f"  {C}›{RS} choose [0-{len(numbered)}]: ").strip()
        except EOFError:
            break
        if raw == "0":
            break

        try:
            choice = int(raw)
            if not 1 <= choice <= len(numbered):
                raise ValueError
        except ValueError:
            print_warn(f"Enter a number between 0 and {len(numbered)}")
            continue

        label, action = numbered[choice - 1]
        print()

        if action == "discover_all":
            devices = await discover(session, timeout=5.0)
            if devices:
                print_ok(f"Found {len(devices)} device(s):")
                _device_table(devices)

        elif action == "discover_range":
            lo = ask_int("Low device ID", 1, 0, 4194303)
            hi = ask_int("High device ID", lo, lo, 4194303)
            devices = await discover(session, low=lo, high=hi, timeout=5.0)
            if devices:
                print_ok(f"Found {len(devices)} device(s):")
                _device_table(devices)

        elif action == "select":
            if not session.devices:
                print_warn("No devices discovered yet.")
            else:
                devs = list(session.devices.values())
                for i, d in enumerate(devs, 1):
                    marker = f"{G}←{RS}" if session.active and session.active.device_id == d.device_id else ""
                    print(f"  {C}{i}{RS}  Device {d.device_id}  {d.name}  {d.vendor}  @ {d.address}  {marker}")
                idx = ask_int("Select device number", 1, 1, len(devs))
                session.active = devs[idx - 1]
                print_ok(f"Active device → {session.active.device_id} ({session.active.name})")

        elif action == "browse":
            if not _need_device(session):
                pass
            else:
                obj_list = await get_object_list(session)
                if obj_list:
                    print_ok(f"{len(obj_list)} object(s) on Device {session.active.device_id}:")
                    _object_table(obj_list)

        elif action == "props":
            if not _need_device(session):
                pass
            else:
                obj_type = ask("Object type (e.g. analog-input)", "analog-input")
                instance = ask_int("Instance", 0, 0, 4194303)
                props = await read_all_props(session, obj_type, instance)
                if props:
                    _props_table(props)

        elif action == "read":
            if not _need_device(session):
                pass
            else:
                obj_type = ask("Object type (e.g. analog-input)", "analog-input")
                instance = ask_int("Instance", 0, 0, 4194303)
                prop     = ask("Property", "presentValue")
                val = await read_prop(session, obj_type, instance, prop)
                if val is not None:
                    print_ok(f"({obj_type},{instance}).{prop} = {Y}{val}{RS}")

        elif action == "write":
            if not _need_device(session):
                pass
            else:
                obj_type  = ask("Object type (e.g. analog-value)", "analog-value")
                instance  = ask_int("Instance", 0, 0, 4194303)
                prop      = ask("Property", "presentValue")
                value_str = ask("Value")
                prio_s    = ask("Priority (1–16, Enter for none)", "")
                try:
                    priority = int(prio_s) if prio_s else None
                except ValueError:
                    priority = None
                ok = await write_prop(session, obj_type, instance, prop, value_str, priority)
                if ok:
                    print_ok(f"Wrote {value_str!r} → ({obj_type},{instance}).{prop}")

        elif action == "cov":
            if not _need_device(session):
                pass
            else:
                obj_type = ask("Object type", "analog-value")
                instance = ask_int("Instance", 0, 0, 4194303)
                lifetime = ask_int("Lifetime (seconds)", 60, 1, 3600)
                await subscribe_cov(session, obj_type, instance, lifetime)

        elif action == "readrange":
            if not _need_device(session):
                pass
            else:
                instance = ask_int("TrendLog instance", 0, 0, 4194303)
                count    = ask_int("Records to fetch", 20, 1, 1000)
                records  = await read_range(session, instance, count)
                if records:
                    for i, rec in enumerate(records):
                        print(f"  {D}{i + 1:>4}{RS}  {rec}")
                else:
                    print_info("No records returned.")

        try:
            input(f"\n  {D}Press Enter to continue …{RS}")
        except EOFError:
            break


# ─── argparse setup ───────────────────────────────────────────────────────────

def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(
        prog="python -m bacnet_explorer",
        description="BACnet/IP Explorer — discover, browse, read, write, subscribe",
    )
    p.add_argument("--ip",   default="", help="local IP/CIDR (auto-detect if omitted)")
    p.add_argument("--port", type=int, default=47808, help="local UDP port (default 47808)")

    sub = p.add_subparsers(dest="command")

    # discover
    d = sub.add_parser("discover", help="WhoIs broadcast or ranged")
    d.add_argument("--range", help="lo:hi device ID range, e.g. 100:200")

    # browse
    b = sub.add_parser("browse", help="list all objects on a device")
    b.add_argument("device_id", type=int)

    # read
    r = sub.add_parser("read", help="read a single property")
    r.add_argument("device_id", type=int)
    r.add_argument("obj_type")
    r.add_argument("instance", type=int)
    r.add_argument("prop")

    # write
    w = sub.add_parser("write", help="write a property value")
    w.add_argument("device_id", type=int)
    w.add_argument("obj_type")
    w.add_argument("instance", type=int)
    w.add_argument("prop")
    w.add_argument("value")
    w.add_argument("--priority", type=int, default=None)

    # props
    pr = sub.add_parser("props", help="read all properties of one object")
    pr.add_argument("device_id", type=int)
    pr.add_argument("obj_type")
    pr.add_argument("instance", type=int)

    # cov
    cv = sub.add_parser("cov", help="subscribe to COV notifications")
    cv.add_argument("device_id", type=int)
    cv.add_argument("obj_type")
    cv.add_argument("instance", type=int)
    cv.add_argument("--lifetime", type=int, default=60)

    # readrange
    rr = sub.add_parser("readrange", help="read TrendLog records via ReadRange")
    rr.add_argument("device_id", type=int)
    rr.add_argument("instance", type=int)
    rr.add_argument("--count", type=int, default=20, help="max records to fetch (default 20)")

    # gui
    g = sub.add_parser("gui", help="launch desktop app (pywebview) or browser GUI")
    g.add_argument("--ip",       default="",   help="local IP/CIDR (auto-detect if omitted)")
    g.add_argument("--port",     type=int, default=47808, help="BACnet UDP port (default 47808)")
    g.add_argument("--web-port", type=int, default=8080,  help="HTTP port for the GUI (default 8080)")
    g.add_argument("--browser",  action="store_true",     help="open system browser instead of native window")
    g.add_argument("--no-browser", action="store_true",   help="(deprecated) alias for --browser")

    return p


# ─── Main ─────────────────────────────────────────────────────────────────────

async def async_main() -> None:
    parser = build_parser()
    args   = parser.parse_args()

    session = Session()
    try:
        session.start(local_ip=args.ip, port=args.port)
    except Exception as exc:
        print_err(f"Failed to start BACnet stack: {exc}")
        sys.exit(1)

    try:
        if args.command is None:
            await run_interactive_menu(session)
        elif args.command == "discover":
            await cmd_discover(session, args)
        elif args.command in ("browse", "read", "write", "props", "cov", "readrange"):
            found = await discover(session, timeout=3.0)
            if not found:
                print_err("No BACnet devices found after 3s broadcast — check network/port.")
                sys.exit(1)
            dispatch = {
                "browse":    cmd_browse,
                "read":      cmd_read,
                "write":     cmd_write,
                "props":     cmd_props,
                "cov":       cmd_cov,
                "readrange": cmd_readrange,
            }
            await dispatch[args.command](session, args)
    except KeyboardInterrupt:
        print()
        print_info("Interrupted.")
    finally:
        session.stop()


def main() -> None:
    # When packaged as a .exe with no arguments, open the desktop app directly.
    if getattr(sys, "frozen", False) and len(sys.argv) == 1:
        launch_app()
        return

    parser = build_parser()
    args, _ = parser.parse_known_args()
    if args.command == "gui":
        args = parser.parse_args()
        use_browser = args.browser or args.no_browser
        if use_browser:
            launch_gui(
                local_ip=args.ip,
                bacnet_port=args.port,
                web_port=args.web_port,
                open_browser=True,
            )
        else:
            launch_app(
                local_ip=args.ip,
                bacnet_port=args.port,
                web_port=args.web_port,
            )
    else:
        asyncio.run(async_main())


if __name__ == "__main__":
    main()
