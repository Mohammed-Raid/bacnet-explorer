from __future__ import annotations
import asyncio

from bacpypes3.primitivedata import ObjectIdentifier
from bacpypes3.pdu import IPv4Address

from bacnet_explorer.session import Session, DeviceInfo
from bacnet_explorer.utils import print_info, print_err, print_warn


async def discover(
    session: Session,
    low: int | None = None,
    high: int | None = None,
    timeout: float = 5.0,
    address: str | None = None,
) -> list[DeviceInfo]:
    """
    Send WhoIs and collect IAm responses.
    address: optional unicast target, e.g. '192.168.1.50:47808'.
             Required when server and client are on the same machine
             because Windows does not loop back UDP broadcasts.
    Populates session.devices. Sets session.active to the first found device
    only if session.active is currently None.
    Returns list of DeviceInfo for all found devices.
    """
    if session.app is None:
        print_err("Session not started.")
        return []

    kwargs: dict = {"timeout": timeout}
    if low is not None and high is not None:
        kwargs["low_limit"]  = low
        kwargs["high_limit"] = high
    if address:
        try:
            kwargs["address"] = IPv4Address(address)
            print_info(f"Sending unicast WhoIs → {address} (timeout={timeout}s) …")
        except Exception as exc:
            print_err(f"Invalid target address {address!r}: {exc}")
            return []
    else:
        print_info(f"Sending broadcast WhoIs (timeout={timeout}s) …")

    try:
        i_ams = await session.app.who_is(**kwargs)
    except Exception as exc:
        print_err(f"WhoIs failed: {exc}")
        return []

    found: list[DeviceInfo] = []
    for iam in (i_ams or []):
        device_id = iam.iAmDeviceIdentifier[1]
        address   = iam.pduSource

        name   = await _read_str(session, address, device_id, "objectName",  f"Device-{device_id}")
        vendor = await _read_str(session, address, device_id, "vendorName",  "Unknown")

        info = DeviceInfo(device_id=device_id, address=address, name=name, vendor=vendor)
        session.devices[device_id] = info
        if session.active is None:
            session.active = info
        found.append(info)

    if not found:
        print_warn("No BACnet devices responded.")

    return found


async def _read_str(
    session: Session,
    address,
    device_id: int,
    prop: str,
    default: str,
) -> str:
    try:
        val = await session.app.read_property(
            address, ObjectIdentifier(("device", device_id)), prop
        )
        return str(val) if val is not None else default
    except Exception:
        return default
