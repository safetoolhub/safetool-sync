import ctypes
from ctypes import wintypes
import os

kernel32 = ctypes.windll.kernel32

GENERIC_READ = 0x80000000
FILE_SHARE_READ = 0x00000001
FILE_SHARE_WRITE = 0x00000002
OPEN_EXISTING = 3
IOCTL_STORAGE_QUERY_PROPERTY = 0x002D1400

class STORAGE_PROPERTY_QUERY(ctypes.Structure):
    _fields_ = [
        ("PropertyId", ctypes.c_int),
        ("QueryType", ctypes.c_int),
        ("AdditionalParameters", ctypes.c_byte * 1)
    ]

class STORAGE_DEVICE_DESCRIPTOR(ctypes.Structure):
    _fields_ = [
        ("Version", ctypes.c_ulong),
        ("Size", ctypes.c_ulong),
        ("DeviceType", ctypes.c_byte),
        ("DeviceTypeModifier", ctypes.c_byte),
        ("RemovableMedia", ctypes.c_byte),
        ("CommandQueueing", ctypes.c_byte),
        ("VendorIdOffset", ctypes.c_ulong),
        ("ProductIdOffset", ctypes.c_ulong),
        ("ProductRevisionOffset", ctypes.c_ulong),
        ("SerialNumberOffset", ctypes.c_ulong),
        ("BusType", ctypes.c_int),
        ("RawPropertiesLength", ctypes.c_ulong),
        ("RawDeviceProperties", ctypes.c_byte * 1)
    ]

def get_bus_type(drive_letter):
    drive_path = f"\\\\.\\{drive_letter[0]}:"
    hDevice = kernel32.CreateFileW(
        drive_path,
        0,
        FILE_SHARE_READ | FILE_SHARE_WRITE,
        None,
        OPEN_EXISTING,
        0,
        None
    )
    if hDevice == -1 or hDevice == 4294967295:
        return "Handle Error"

    query = STORAGE_PROPERTY_QUERY()
    query.PropertyId = 0
    query.QueryType = 0

    out_buffer = STORAGE_DEVICE_DESCRIPTOR()
    bytes_returned = wintypes.DWORD()

    result = kernel32.DeviceIoControl(
        hDevice,
        IOCTL_STORAGE_QUERY_PROPERTY,
        ctypes.byref(query),
        ctypes.sizeof(query),
        ctypes.byref(out_buffer),
        ctypes.sizeof(out_buffer),
        ctypes.byref(bytes_returned),
        None
    )
    kernel32.CloseHandle(hDevice)

    if result:
        return out_buffer.BusType
    return "IoControl Error"

for d in "CDEFP":
    print(d, get_bus_type(d))
