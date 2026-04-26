from __future__ import annotations
from typing import Any

from bacpypes3.primitivedata import (
    ObjectIdentifier, Real, Unsigned, Integer, CharacterString, Boolean
)
from bacpypes3.basetypes import BinaryPV
try:
    from bacpypes3.basetypes import RangeByPosition
except ImportError:
    from bacpypes3.apdu import RangeByPosition  # location varies by bacpypes3 version

from bacnet_explorer.session import Session
from bacnet_explorer.utils import print_err, print_info, print_warn


def _coerce(value_str: str) -> Any:
    """Convert a string to the most likely BACnet primitive type."""
    v = value_str.strip()
    if v.lower() in ("active", "inactive"):
        return BinaryPV(v.lower())
    if v.lower() == "true":
        return Boolean(True)
    if v.lower() == "false":
        return Boolean(False)
    # Unsigned / Integer (no decimal point)
    if "." not in v:
        try:
            iv = int(v)
            return Unsigned(iv) if iv >= 0 else Integer(iv)
        except ValueError:
            pass
    # Real (has decimal point)
    try:
        return Real(float(v))
    except ValueError:
        pass
    # Fallback
    return CharacterString(v)


async def read_prop(
    session: Session,
    obj_type: str,
    instance: int,
    prop: str,
) -> Any:
    """Read a single BACnet property. Returns value or None on error."""
    if session.app is None:
        print_err("Session not started.")
        return None
    if session.active is None:
        print_err("No active device.")
        return None
    try:
        return await session.app.read_property(
            session.active.address,
            ObjectIdentifier((obj_type, instance)),
            prop,
        )
    except BaseException as exc:
        if isinstance(exc, (KeyboardInterrupt, SystemExit)): raise
        print_err(f"ReadProperty ({obj_type},{instance}).{prop}: {exc}")
        return None


async def write_prop(
    session: Session,
    obj_type: str,
    instance: int,
    prop: str,
    value_str: str,
    priority: int | None = None,
) -> bool:
    """
    Write a BACnet property. Auto-coerces value_str to the right type.
    Returns True on success.
    """
    if session.app is None:
        print_err("Session not started.")
        return False
    if session.active is None:
        print_err("No active device.")
        return False

    value = _coerce(value_str)
    kwargs: dict = {}
    if priority is not None:
        if not 1 <= priority <= 16:
            print_warn("Priority must be 1–16. Using 16.")
            priority = 16
        kwargs["priority"] = priority

    try:
        await session.app.write_property(
            session.active.address,
            ObjectIdentifier((obj_type, instance)),
            prop,
            value,
            **kwargs,
        )
        return True
    except BaseException as exc:
        if isinstance(exc, (KeyboardInterrupt, SystemExit)): raise
        print_err(f"WriteProperty ({obj_type},{instance}).{prop}: {exc}")
        if "out-of-service" in str(exc).lower():
            print_info("Hint: check that outOfService is False on this object.")
        if "priority" in str(exc).lower():
            print_info("Hint: try a higher-priority write (lower number, e.g. --priority 8).")
        return False


async def read_range(session: Session, instance: int, count: int = 20) -> list:
    """
    ReadRange on trendLog,<instance> logBuffer, up to <count> records from position 1.
    Returns list of log records or empty list on error.
    """
    if session.app is None:
        print_err("Session not started.")
        return []
    if session.active is None:
        print_err("No active device.")
        return []

    obj_id = ObjectIdentifier(("trend-log", instance))
    try:
        records = await session.app.read_range(
            session.active.address,
            obj_id,
            "logBuffer",
            RangeByPosition(1, count),
        )
        return list(records) if records else []
    except AttributeError:
        print_warn("bacpypes3 read_range not available in this version.")
        return []
    except BaseException as exc:
        if isinstance(exc, (KeyboardInterrupt, SystemExit)): raise
        print_err(f"ReadRange trendLog,{instance}: {exc}")
        return []
