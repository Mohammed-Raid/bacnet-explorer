from __future__ import annotations
import asyncio
from datetime import datetime

from bacpypes3.primitivedata import ObjectIdentifier

from bacnet_explorer.session import Session
from bacnet_explorer.utils import print_info, print_err, print_warn, print_ok, Y, RS


async def subscribe_cov(
    session: Session,
    obj_type: str,
    instance: int,
    lifetime: int = 60,
) -> None:
    """
    Subscribe to COV notifications for an object and print each notification
    with a timestamp until lifetime (seconds) expires or the user presses Ctrl+C.
    """
    if session.app is None:
        print_err("Session not started.")
        return
    if session.active is None:
        print_err("No active device.")
        return

    address = session.active.address
    obj_id  = ObjectIdentifier((obj_type, instance))

    try:
        await session.app.subscribe_cov(
            address                     = address,
            monitoredObjectIdentifier   = obj_id,
            issueConfirmedNotifications = True,
            lifetime                    = lifetime,
        )
    except AttributeError:
        print_warn("subscribe_cov not available in this bacpypes3 build.")
        return
    except Exception as exc:
        print_err(f"SubscribeCOV failed: {exc}")
        return

    # Register notification handler only after the subscription is confirmed.
    notif_queue: asyncio.Queue = asyncio.Queue()

    async def _handle_cov(apdu) -> None:
        await notif_queue.put(apdu)

    _attr  = "do_ConfirmedCOVNotificationRequest"
    _saved = getattr(session.app, _attr, None)
    setattr(session.app, _attr, _handle_cov)

    print_ok(
        f"COV subscription active: {obj_type},{instance}  "
        f"lifetime={lifetime}s"
    )
    print_info("Notifications will appear below. Ctrl+C to stop early.\n")

    loop     = asyncio.get_running_loop()
    deadline = loop.time() + lifetime
    try:
        while True:
            remaining = deadline - loop.time()
            if remaining <= 0:
                break
            try:
                apdu = await asyncio.wait_for(notif_queue.get(), timeout=min(1.0, remaining))
                ts = datetime.now().strftime("%H:%M:%S")
                for prop_val in getattr(apdu, "listOfValues", []):
                    prop_id = getattr(prop_val, "propertyIdentifier", "?")
                    value   = getattr(prop_val, "value", "?")
                    print(f"  {Y}{ts}{RS}  {prop_id} = {value}")
            except asyncio.TimeoutError:
                pass
    except (KeyboardInterrupt, asyncio.CancelledError):
        pass
    finally:
        if _saved is not None:
            setattr(session.app, _attr, _saved)
        elif hasattr(session.app, _attr):
            delattr(session.app, _attr)

    print_info("COV subscription ended.")
