from __future__ import annotations
from dataclasses import dataclass

from bacpypes3.local.device import DeviceObject
from bacpypes3.ipv4.app import NormalApplication
from bacpypes3.primitivedata import Unsigned
from bacpypes3.basetypes import Segmentation
from bacpypes3.pdu import IPv4Address

from bacnet_explorer.utils import detect_local_ip, print_info, print_ok, print_err

CLIENT_DEVICE_ID = 55900
BACNET_PORT      = 47808


@dataclass
class DeviceInfo:
    device_id: int
    address: IPv4Address
    name: str
    vendor: str


class Session:
    def __init__(self) -> None:
        self.app: NormalApplication | None = None
        self.local_ip: str = ""
        self.devices: dict[int, DeviceInfo] = {}
        self.active: DeviceInfo | None = None

    def start(self, local_ip: str = "", port: int = BACNET_PORT) -> None:
        import socket as _socket
        # Fail fast if the port is already in use (stale process, other BACnet app).
        probe = _socket.socket(_socket.AF_INET, _socket.SOCK_DGRAM)
        try:
            probe.bind(("", port))
        except OSError:
            probe.close()
            raise RuntimeError(
                f"UDP port {port} is already in use.\n"
                f"Close any other BACnet application (or a previous instance of this app) and try again."
            )
        probe.close()

        self.local_ip = local_ip or detect_local_ip()
        cidr = self.local_ip if "/" in self.local_ip else f"{self.local_ip}/24"
        addr = IPv4Address(f"{cidr}:{port}")
        device = DeviceObject(
            objectIdentifier           = ("device", CLIENT_DEVICE_ID),
            objectName                 = "BACnetExplorer",
            vendorIdentifier           = Unsigned(15),
            maxApduLengthAccepted      = Unsigned(1024),
            segmentationSupported      = Segmentation("segmentedBoth"),
        )
        self.app = NormalApplication(device, addr)
        print_ok(f"BACnet/IP stack ready on {self.local_ip}:{port}")

    def stop(self) -> None:
        if self.app:
            self.app.close()
            self.app = None
        print_info("Session closed.")
