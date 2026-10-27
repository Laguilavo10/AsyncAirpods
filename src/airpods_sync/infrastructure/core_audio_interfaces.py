"""COM declarations from the Windows SDK that pycaw does not ship.

Only the vtable entries up to the last method we call are typed precisely;
the rest use opaque pointers. The method order must match the SDK headers
(devicetopology.h, ks.h, ksmedia.h).
"""

from __future__ import annotations

from ctypes import HRESULT, POINTER, Structure, c_int, c_uint, c_ulong, c_void_p, c_wchar_p

from comtypes import COMMETHOD, GUID, IUnknown

# ksmedia.h: KSPROPSETID_BtAudio and its KSPROPERTY_BTAUDIO ids
KSPROPSETID_BT_AUDIO = GUID("{7FA06C40-B8F6-4C7E-8556-E8C33A12E54D}")
KSPROPERTY_ONESHOT_RECONNECT = 0
KSPROPERTY_ONESHOT_DISCONNECT = 1
KSPROPERTY_TYPE_GET = 0x1


class KSPROPERTY(Structure):
    _fields_ = [("Set", GUID), ("Id", c_ulong), ("Flags", c_ulong)]


class IKsControl(IUnknown):
    _iid_ = GUID("{28F54685-06FD-11D2-B27A-00A0C9223196}")
    _methods_ = [
        COMMETHOD(
            [], HRESULT, "KsProperty",
            (["in"], POINTER(KSPROPERTY), "Property"),
            (["in"], c_ulong, "PropertyLength"),
            (["in"], c_void_p, "PropertyData"),
            (["in"], c_ulong, "DataLength"),
            (["out"], POINTER(c_ulong), "BytesReturned"),
        ),
    ]


class IConnector(IUnknown):
    _iid_ = GUID("{9C2C4058-23F5-41DE-877A-DF3AF236A09E}")


class IPart(IUnknown):
    _iid_ = GUID("{AE2DE0E4-5BCA-4F2D-AA46-5D13F8FDB3A9}")


class IDeviceTopology(IUnknown):
    _iid_ = GUID("{2A07407E-6497-4A18-9787-32F79BD0D98F}")


IConnector._methods_ = [
    COMMETHOD([], HRESULT, "GetType", (["out"], POINTER(c_int), "pType")),
    COMMETHOD([], HRESULT, "GetDataFlow", (["out"], POINTER(c_int), "pFlow")),
    COMMETHOD([], HRESULT, "ConnectTo", (["in"], POINTER(IConnector), "pConnectTo")),
    COMMETHOD([], HRESULT, "Disconnect"),
    COMMETHOD([], HRESULT, "IsConnected", (["out"], POINTER(c_int), "pbConnected")),
    COMMETHOD([], HRESULT, "GetConnectedTo", (["out"], POINTER(POINTER(IConnector)), "ppConTo")),
    COMMETHOD([], HRESULT, "GetConnectorIdConnectedTo", (["out"], POINTER(c_wchar_p), "ppwstrConnectorId")),
    COMMETHOD([], HRESULT, "GetDeviceIdConnectedTo", (["out"], POINTER(c_wchar_p), "ppwstrDeviceId")),
]

IPart._methods_ = [
    COMMETHOD([], HRESULT, "GetName", (["out"], POINTER(c_wchar_p), "ppwstrName")),
    COMMETHOD([], HRESULT, "GetLocalId", (["out"], POINTER(c_uint), "pnId")),
    COMMETHOD([], HRESULT, "GetGlobalId", (["out"], POINTER(c_wchar_p), "ppwstrGlobalId")),
    COMMETHOD([], HRESULT, "GetPartType", (["out"], POINTER(c_int), "pPartType")),
    COMMETHOD([], HRESULT, "GetSubType", (["out"], POINTER(GUID), "pSubType")),
    COMMETHOD([], HRESULT, "GetControlInterfaceCount", (["out"], POINTER(c_uint), "pCount")),
    COMMETHOD(
        [], HRESULT, "GetControlInterface",
        (["in"], c_uint, "nIndex"),
        (["out"], POINTER(c_void_p), "ppInterfaceDesc"),
    ),
    COMMETHOD([], HRESULT, "EnumPartsIncoming", (["out"], POINTER(c_void_p), "ppParts")),
    COMMETHOD([], HRESULT, "EnumPartsOutgoing", (["out"], POINTER(c_void_p), "ppParts")),
    COMMETHOD(
        [], HRESULT, "GetTopologyObject",
        (["out"], POINTER(POINTER(IDeviceTopology)), "ppTopology"),
    ),
    COMMETHOD(
        [], HRESULT, "Activate",
        (["in"], c_ulong, "dwClsContext"),
        (["in"], POINTER(GUID), "refiid"),
        (["out"], POINTER(POINTER(IUnknown)), "ppvObject"),
    ),
]

IDeviceTopology._methods_ = [
    COMMETHOD([], HRESULT, "GetConnectorCount", (["out"], POINTER(c_uint), "pCount")),
    COMMETHOD(
        [], HRESULT, "GetConnector",
        (["in"], c_uint, "nIndex"),
        (["out"], POINTER(POINTER(IConnector)), "ppConnector"),
    ),
    COMMETHOD([], HRESULT, "GetSubunitCount", (["out"], POINTER(c_uint), "pCount")),
    COMMETHOD(
        [], HRESULT, "GetSubunit",
        (["in"], c_uint, "nIndex"),
        (["out"], POINTER(c_void_p), "ppSubunit"),
    ),
    COMMETHOD(
        [], HRESULT, "GetPartById",
        (["in"], c_uint, "nId"),
        (["out"], POINTER(POINTER(IPart)), "ppPart"),
    ),
    COMMETHOD([], HRESULT, "GetDeviceId", (["out"], POINTER(c_wchar_p), "ppwstrDeviceId")),
]
