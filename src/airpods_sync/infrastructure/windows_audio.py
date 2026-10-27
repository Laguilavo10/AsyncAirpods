"""Windows Core Audio adapters: audio activity and Bluetooth headset connection.

Connecting uses the same approach as ToothTray: every Bluetooth audio endpoint
is backed by a kernel-streaming filter from the Bluetooth audio driver, and
that filter accepts the KSPROPSETID_BtAudio one-shot reconnect/disconnect
properties, which make Windows open or close the headset's audio connection.
"""

from __future__ import annotations

import re
import warnings
from ctypes import byref, sizeof
from dataclasses import dataclass

import comtypes
from comtypes import COMError
from pycaw.api.endpointvolume import IAudioMeterInformation
from pycaw.constants import EDataFlow, ERole
from pycaw.utils import AudioUtilities

from airpods_sync.application.ports import BluetoothAudioDevice, DeviceNotFoundError, HeadsetControlError
from airpods_sync.infrastructure.core_audio_interfaces import (
    KSPROPERTY,
    KSPROPERTY_ONESHOT_DISCONNECT,
    KSPROPERTY_ONESHOT_RECONNECT,
    KSPROPERTY_TYPE_GET,
    KSPROPSETID_BT_AUDIO,
    IDeviceTopology,
    IKsControl,
)

_DEVICE_STATE_ACTIVE = 0x1
_DEVICE_STATE_UNPLUGGED = 0x8  # paired Bluetooth headsets that are not connected
_PKEY_DEVICE_INTERFACE_FRIENDLY_NAME = "{026E516E-B814-414B-83CD-856D6FEF4822} 2"
_BLUETOOTH_FILTER_MARKER = "?\\BTH"  # filter IDs look like {2}.\\?\bthenum#...
# Stereo filter IDs carry the vendor and product: ..._vid&0001004c_pid&2027#...
_APPLE_PRODUCT_ID = re.compile(r"_vid&0001004c_pid&([0-9a-f]{4})", re.IGNORECASE)


class CoreAudioActivityMonitor:
    def __init__(self, peak_threshold: float = 0.01) -> None:
        self._enumerator = AudioUtilities.GetDeviceEnumerator()
        self._peak_threshold = peak_threshold

    def is_playing(self) -> bool:
        try:
            # Looked up every time: the default device changes when a headset connects
            speakers = self._enumerator.GetDefaultAudioEndpoint(EDataFlow.eRender.value, ERole.eMultimedia.value)
            meter = speakers.Activate(IAudioMeterInformation._iid_, comtypes.CLSCTX_ALL, None)
            return meter.QueryInterface(IAudioMeterInformation).GetPeakValue() > self._peak_threshold
        except COMError:
            return False  # no output device


@dataclass(frozen=True)
class _EndpointInfo:
    device_name: str
    filter_id: str

    @property
    def model_id(self) -> int | None:
        match = _APPLE_PRODUCT_ID.search(self.filter_id)
        return int(match.group(1), 16) if match else None


class CoreAudioHeadsetController:
    def __init__(self) -> None:
        self._enumerator = AudioUtilities.GetDeviceEnumerator()
        # endpoint ID -> info, or None for non-Bluetooth endpoints; reading it is slow
        self._endpoint_info: dict[str, _EndpointInfo | None] = {}

    def list_devices(self) -> list[BluetoothAudioDevice]:
        connected: dict[str, bool] = {}
        model_ids: dict[str, int] = {}
        for info, is_active in self._bluetooth_endpoints():
            connected[info.device_name] = connected.get(info.device_name, False) or is_active
            if info.model_id is not None:  # only the stereo filter reports it
                model_ids[info.device_name] = info.model_id
        return [
            BluetoothAudioDevice(name, is_connected, model_ids.get(name))
            for name, is_connected in sorted(connected.items())
        ]

    def connect(self, name: str) -> None:
        self._send(name, KSPROPERTY_ONESHOT_RECONNECT)

    def disconnect(self, name: str) -> None:
        self._send(name, KSPROPERTY_ONESHOT_DISCONNECT)

    def _send(self, name: str, property_id: int) -> None:
        filter_ids = {info.filter_id for info, _ in self._bluetooth_endpoints() if info.device_name == name}
        if not filter_ids:
            raise DeviceNotFoundError(f"'{name}' is not a paired Bluetooth audio device.")

        request = KSPROPERTY(KSPROPSETID_BT_AUDIO, property_id, KSPROPERTY_TYPE_GET)
        errors: list[COMError] = []
        for filter_id in filter_ids:
            try:
                device = self._enumerator.GetDevice(filter_id)
                control = device.Activate(IKsControl._iid_, comtypes.CLSCTX_ALL, None).QueryInterface(IKsControl)
                control.KsProperty(byref(request), sizeof(request), None, 0)
            except COMError as error:
                errors.append(error)

        # A headset exposes one filter per profile (stereo and hands-free). Asking both
        # matters: stereo alone took ~9-11 s to connect, both together ~4 s, like
        # Windows' own Connect button. One accepted request is enough to proceed.
        if len(errors) == len(filter_ids):
            raise HeadsetControlError(f"Windows rejected the request for '{name}': {errors[0]}")

    def _bluetooth_endpoints(self) -> list[tuple[_EndpointInfo, bool]]:
        # All data flows: the hands-free filter may only be reachable from its microphone endpoint
        collection = self._enumerator.EnumAudioEndpoints(
            EDataFlow.eAll.value, _DEVICE_STATE_ACTIVE | _DEVICE_STATE_UNPLUGGED
        )
        endpoints = []
        for index in range(collection.GetCount()):
            device = collection.Item(index)
            endpoint_id = device.GetId()
            if endpoint_id not in self._endpoint_info:
                self._endpoint_info[endpoint_id] = self._read_info(device)
            info = self._endpoint_info[endpoint_id]
            if info is not None:
                endpoints.append((info, device.GetState() == _DEVICE_STATE_ACTIVE))
        return endpoints

    @staticmethod
    def _read_info(device) -> _EndpointInfo | None:
        try:
            topology = device.Activate(IDeviceTopology._iid_, comtypes.CLSCTX_ALL, None)
            filter_id = topology.QueryInterface(IDeviceTopology).GetConnector(0).GetDeviceIdConnectedTo()
        except COMError:
            return None
        if _BLUETOOTH_FILTER_MARKER not in filter_id.upper():
            return None

        with warnings.catch_warnings():
            warnings.simplefilter("ignore")  # pycaw warns about unreadable properties
            properties = AudioUtilities.CreateDevice(device).properties
        name = (properties.get(_PKEY_DEVICE_INTERFACE_FRIENDLY_NAME) or "").strip()
        return _EndpointInfo(name, filter_id) if name else None
