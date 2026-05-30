# This file is part of SafeTool Sync, licensed under GPLv3 with
# additional terms. See LICENSE or https://safetoolhub.org for details.
"""Disk detector — detects external/removable drives using psutil."""
from __future__ import annotations

import platform
import subprocess
from typing import Any

from services.models import DiskInfo

try:
    import psutil
except ImportError:
    psutil = None  # type: ignore[assignment]


def detect_external_drives() -> list[DiskInfo]:
    """Detect externally mounted drives (USB, external HDD, SD cards).

    Returns:
        List of DiskInfo for each detected external drive.
    """
    if psutil is None:
        return []

    drives: list[DiskInfo] = []
    seen_devices: set[str] = set()

    for partition in psutil.disk_partitions(all=True):
        try:
            usage = psutil.disk_usage(partition.mountpoint)
        except (PermissionError, OSError):
            continue

        if not _is_external(partition):
            continue

        if partition.device in seen_devices:
            continue
        seen_devices.add(partition.device)

        label = _get_label(partition)
        uuid_or_serial = _get_uuid(partition)

        drive_info = DiskInfo(
            mount_point=partition.mountpoint,
            label=label,
            total_bytes=usage.total,
            free_bytes=usage.free,
            fstype=partition.fstype,
            device=partition.device,
            uuid_or_serial=uuid_or_serial,
        )
        drives.append(drive_info)

    return drives


def _is_virtual_linux(partition: Any) -> bool:
    if platform.system() != "Linux":
        return False
    mount = partition.mountpoint
    if mount.startswith(('/sys', '/proc', '/dev', '/run', '/snap', '/tmp', '/var/lib/docker', '/var/snap')):
        if not mount.startswith('/run/media/'):
            return True
    virtual_fs = {
        'tmpfs', 'squashfs', 'overlay', 'aufs', 'devtmpfs', 'proc', 'sysfs', 'cgroup2', 
        'pstore', 'efivarfs', 'bpf', 'mqueue', 'hugetlbfs', 'debugfs', 'tracefs', 
        'fusectl', 'configfs', 'binfmt_misc', 'securityfs', 'autofs'
    }
    if partition.fstype in virtual_fs:
        return True
    return False


def get_all_drives() -> list[DiskInfo]:
    """Get all mounted drives (internal + external).

    Returns:
        List of DiskInfo for all mounted drives.
    """
    if psutil is None:
        return []

    drives: list[DiskInfo] = []
    seen_devices: set[str] = set()

    for partition in psutil.disk_partitions(all=True):
        if _is_virtual_linux(partition):
            continue

        try:
            usage = psutil.disk_usage(partition.mountpoint)
        except (PermissionError, OSError):
            continue

        if partition.device in seen_devices:
            continue
        seen_devices.add(partition.device)

        label = _get_label(partition)
        uuid_or_serial = _get_uuid(partition)

        drive_info = DiskInfo(
            mount_point=partition.mountpoint,
            label=(label if label else partition.mountpoint),
            total_bytes=usage.total,
            free_bytes=usage.free,
            fstype=partition.fstype,
            device=partition.device,
            uuid_or_serial=uuid_or_serial,
        )
        drives.append(drive_info)

    return drives


def get_drive_for_path(path: str) -> DiskInfo | None:
    """Find the mounted drive that contains the given path.

    Matches the path against all mounted drives and returns the DiskInfo of the
    drive with the longest matching mount point (most specific mount).

    Args:
        path: Absolute filesystem path.

    Returns:
        DiskInfo of the containing drive, or None if not found.
    """
    if psutil is None or not path:
        return None

    import os
    try:
        abs_path = os.path.abspath(path)
    except (OSError, ValueError):
        return None

    best: DiskInfo | None = None
    best_len = -1

    for drive in get_all_drives():
        mount = drive.mount_point
        try:
            norm_mount = os.path.abspath(mount)
        except (OSError, ValueError):
            continue

        if _path_under_mount(abs_path, norm_mount) and len(norm_mount) > best_len:
            best = drive
            best_len = len(norm_mount)

    return best


def _path_under_mount(abs_path: str, mount: str) -> bool:
    """Return True if abs_path is located under the mount point."""
    import os
    try:
        common = os.path.commonpath([abs_path, mount])
    except ValueError:
        return False
    return common == mount


def _is_windows_external_bus(mountpoint: str) -> bool:
    """Check if the drive is on a USB or SD bus using DeviceIoControl."""
    try:
        import ctypes
        from ctypes import wintypes
        
        kernel32 = ctypes.windll.kernel32
        
        OPEN_EXISTING = 3
        FILE_SHARE_READ = 1
        FILE_SHARE_WRITE = 2
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
        
        drive_letter = mountpoint[0].upper()
        drive_path = f"\\\\.\\{drive_letter}:"
        
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
            return False
            
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
            # BusType 7 is USB, 12 is SD
            return out_buffer.BusType in (7, 12)
            
    except Exception:
        pass
        
    return False


def _is_external(partition: Any) -> bool:
    """Determine if a partition is an external/removable drive."""
    system = platform.system()

    if system == "Windows":
        opts = partition.opts.lower() if partition.opts else ""
        if "removable" in opts:
            return True
        return _is_windows_external_bus(partition.mountpoint)

    mount = partition.mountpoint

    if system == "Darwin":
        return mount.startswith("/Volumes/") and not mount.startswith("/Volumes/Macintosh")

    return (
        mount.startswith("/media/")
        or mount.startswith("/mnt/")
        or mount.startswith("/run/media/")
    )


def _get_label(partition: Any) -> str:
    """Get the volume label for a partition."""
    system = platform.system()
    mount = partition.mountpoint

    if system == "Windows":
        try:
            import ctypes
            label = ctypes.create_unicode_buffer(256)
            ctypes.windll.kernel32.GetVolumeInformationW(
                mount, label, 256, None, None, None, None, 0,
            )
            if label.value:
                return label.value
        except Exception:
            pass
    elif system == "Darwin":
        try:
            result = subprocess.run(
                ["diskutil", "info", mount],
                capture_output=True, text=True, timeout=5,
            )
            for line in result.stdout.splitlines():
                if "Volume Name" in line:
                    return line.split(":")[-1].strip()
        except Exception:
            pass
    else:
        try:
            import os
            real = os.path.realpath(mount)
            return os.path.basename(real) or os.path.basename(mount)
        except OSError:
            pass

    return partition.mountpoint


def _get_uuid(partition: Any) -> str:
    """Get UUID/serial for a partition."""
    system = platform.system()
    mount = partition.mountpoint

    if system == "Linux":
        try:
            result = subprocess.run(
                ["lsblk", "-no", "MOUNTPOINT,UUID", "-r"],
                capture_output=True, text=True, timeout=5,
            )
            for line in result.stdout.splitlines():
                parts = line.strip().split()
                if len(parts) >= 2 and parts[0] == mount:
                    return parts[1]
        except Exception:
            pass
    elif system == "Darwin":
        try:
            result = subprocess.run(
                ["diskutil", "info", mount],
                capture_output=True, text=True, timeout=5,
            )
            for line in result.stdout.splitlines():
                if "Volume UUID" in line:
                    return line.split(":")[-1].strip()
        except Exception:
            pass
    elif system == "Windows":
        try:
            import ctypes
            serial = ctypes.c_uint32()
            ctypes.windll.kernel32.GetVolumeInformationW(
                mount, None, 0, ctypes.byref(serial), None, None, None, 0,
            )
            return str(serial.value)
        except Exception:
            pass

    return ""