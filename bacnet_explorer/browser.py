from __future__ import annotations
from typing import Any

from bacpypes3.primitivedata import ObjectIdentifier

from bacnet_explorer.session import Session
from bacnet_explorer.utils import print_info, print_err

# bacpypes3.primitivedata.Error (BACnet error PDUs) inherits from BaseException
# directly, not from Exception.  asyncio.CancelledError is also BaseException in
# Python 3.8+.  Catch all of these without swallowing KeyboardInterrupt/SystemExit.
_FATAL = (KeyboardInterrupt, SystemExit)


def _absorb(exc: BaseException) -> None:
    """Re-raise only truly fatal exceptions; swallow everything else."""
    if isinstance(exc, _FATAL):
        raise


async def get_object_list(session: Session) -> list[ObjectIdentifier]:
    """
    Read the objectList property of the active device.
    Returns a list of ObjectIdentifier tuples.
    """
    if session.app is None:
        print_err("Session not started.")
        return []
    if session.active is None:
        print_err("No active device. Discover first.")
        return []

    address   = session.active.address
    device_id = session.active.device_id

    try:
        obj_list = await session.app.read_property(
            address,
            ObjectIdentifier(("device", device_id)),
            "objectList",
        )
        return list(obj_list) if obj_list else []
    except BaseException as exc:
        _absorb(exc)
        print_err(f"ReadProperty objectList: {exc}")
        return []


async def read_all_props(
    session: Session,
    obj_type: str,
    instance: int,
) -> dict[str, Any]:
    """
    Read all properties of an object.
    1. Tries ReadPropertyMultiple with 'all'.
    2. Falls back to reading propertyList then looping ReadProperty.
    """
    if session.app is None:
        print_err("Session not started.")
        return {}
    if session.active is None:
        print_err("No active device.")
        return {}

    address = session.active.address
    obj_id  = ObjectIdentifier((obj_type, instance))

    # ── Attempt 1: ReadPropertyMultiple ─────────────────────────────
    rpm_failed = False
    try:
        result = await session.app.read_property_multiple(
            address,
            [(obj_id, [("all", None)])],
        )
    except BaseException as exc:
        _absorb(exc)
        rpm_failed = True
        result = None

    if not rpm_failed and result:
        try:
            props: dict[str, Any] = {}
            for _obj_id, prop_results in result:
                for prop_ref, value in prop_results:
                    props[str(prop_ref.propertyIdentifier)] = value
            if props:
                return props
        except BaseException as exc:
            _absorb(exc)  # parse error — fall through to per-property loop

    print_info("ReadPropertyMultiple not supported — falling back to propertyList loop.")

    # ── Attempt 2: Read propertyList, then each property ────────────
    prop_names: list[str] = []
    try:
        prop_list = await session.app.read_property(address, obj_id, "propertyList")
        prop_names = [str(p) for p in (prop_list or [])]
    except BaseException as exc:
        _absorb(exc)

    # Always include these core properties even if propertyList failed
    for core in ("objectName", "objectType", "presentValue", "description",
                 "units", "statusFlags", "eventState", "outOfService"):
        if core not in prop_names:
            prop_names.append(core)

    props = {}
    for prop in prop_names:
        try:
            val = await session.app.read_property(address, obj_id, prop)
            if val is not None:
                props[prop] = val
        except BaseException as exc:
            _absorb(exc)
    return props
