import socket

try:
    import colorama
    colorama.init(autoreset=True)
    Y  = colorama.Fore.YELLOW + colorama.Style.BRIGHT   # amber accent
    C  = colorama.Fore.CYAN                              # keys / numbers
    G  = colorama.Fore.GREEN                             # ok / values
    R  = colorama.Fore.RED                               # errors
    D  = colorama.Style.DIM                              # muted labels
    B  = colorama.Style.BRIGHT                           # bold
    RS = colorama.Style.RESET_ALL
except ImportError:
    Y = C = G = R = D = B = RS = ""


def print_ok(msg: str)   -> None: print(f"  {G}✓{RS}  {msg}")
def print_err(msg: str)  -> None: print(f"  {R}✗{RS}  {msg}")
def print_info(msg: str) -> None: print(f"  {D}·{RS}  {msg}")
def print_warn(msg: str) -> None: print(f"  {Y}!{RS}  {msg}")


def print_table(headers: list[str], rows: list[list[str]]) -> None:
    if not rows:
        print(f"  {D}(none){RS}")
        return
    if rows and any(len(row) != len(headers) for row in rows):
        raise ValueError(f"Each row must have {len(headers)} cells, got rows with different lengths")
    widths = [
        max(len(str(h)), max((len(str(r[i])) for r in rows), default=0))
        for i, h in enumerate(headers)
    ]
    top = "  ┌─" + "─┬─".join("─" * w for w in widths) + "─┐"
    sep = "  ├─" + "─┼─".join("─" * w for w in widths) + "─┤"
    bot = "  └─" + "─┴─".join("─" * w for w in widths) + "─┘"

    def fmt(cells: list, color: str = "") -> str:
        parts = [f"{color}{str(c):<{widths[i]}}{RS}" for i, c in enumerate(cells)]
        return "  │ " + " │ ".join(parts) + " │"

    print(top)
    print(fmt(headers, Y))
    print(sep)
    for row in rows:
        print(fmt(row, D))
    print(bot)


def print_banner(session) -> None:
    dev_count = len(session.devices)
    active    = f"Device {session.active.device_id}" if session.active else "none"
    line1     = f"bacnet.explorer  │  {session.local_ip}"
    line2     = f"Devices: {dev_count:<3}      │  Active: {active}"
    width     = max(len(line1), len(line2)) + 2
    print(f"\n  {Y}╔{'═' * width}╗{RS}")
    print(f"  {Y}║{RS}  {B}{line1:<{width - 2}}{RS}  {Y}║{RS}")
    print(f"  {Y}║{RS}  {line2:<{width - 2}}  {Y}║{RS}")
    print(f"  {Y}╚{'═' * width}╝{RS}\n")


def detect_local_ip() -> str:
    try:
        with socket.socket(socket.AF_INET, socket.SOCK_DGRAM) as s:
            s.connect(("8.8.8.8", 80))
            ip = s.getsockname()[0]
    except Exception:
        return "0.0.0.0/24"

    try:
        import ifaddr
        for adapter in ifaddr.get_adapters():
            for a in adapter.ips:
                if isinstance(a.ip, str) and a.ip == ip:
                    return f"{ip}/{a.network_prefix}"
    except Exception:
        pass

    return f"{ip}/24"


def ask(prompt: str, default: str = "") -> str:
    suffix = f" [{default}]" if default else ""
    try:
        v = input(f"  {C}›{RS} {prompt}{suffix}: ").strip()
        return v if v else default
    except EOFError:
        return default


def ask_int(prompt: str, default: int, lo: int, hi: int) -> int:
    if lo > hi:
        raise ValueError(f"lo ({lo}) must be <= hi ({hi})")
    while True:
        try:
            v = int(ask(prompt, str(default)))
            if lo <= v <= hi:
                return v
        except ValueError:
            pass
        print_warn(f"Enter an integer between {lo} and {hi}")


def ask_float(prompt: str, default: float, lo: float, hi: float) -> float:
    if lo > hi:
        raise ValueError(f"lo ({lo}) must be <= hi ({hi})")
    while True:
        try:
            v = float(ask(prompt, str(default)))
            if lo <= v <= hi:
                return v
        except ValueError:
            pass
        print_warn(f"Enter a number between {lo} and {hi}")
