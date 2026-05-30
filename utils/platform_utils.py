# This file is part of SafeTool Sync, licensed under GPLv3 with
# additional terms. See LICENSE or https://safetoolhub.org for details.
"""Platform utilities for SafeTool Sync."""
from __future__ import annotations

import os
import platform
import subprocess
import sys
from typing import Any


def get_cpu_count() -> int:
    return os.cpu_count() or 4


def get_system_ram_gb() -> float:
    try:
        import psutil
        return round(psutil.virtual_memory().total / (1024 ** 3), 1)
    except ImportError:
        return 0.0


def get_system_info() -> dict[str, Any]:
    import psutil

    return {
        "os": platform.system(),
        "os_version": platform.version(),
        "os_release": platform.release(),
        "arch": platform.machine(),
        "python": sys.version,
        "cpu_count": get_cpu_count(),
        "ram_gb": get_system_ram_gb(),
        "hostname": platform.node(),
        "psutil_version": psutil.__version__,
    }


def get_mounted_drives() -> list[dict[str, Any]]:
    import psutil

    drives = []
    seen = set()
    for partition in psutil.disk_partitions(all=True):
        try:
            usage = psutil.disk_usage(partition.mountpoint)
            if partition.mountpoint in seen:
                continue
            seen.add(partition.mountpoint)
            drives.append({
                "mount_point": partition.mountpoint,
                "device": partition.device,
                "fstype": partition.fstype,
                "total_bytes": usage.total,
                "free_bytes": usage.free,
                "used_bytes": usage.used,
            })
        except (PermissionError, OSError):
            continue
    return drives


def get_drive_label(mount_point: str) -> str:
    system = platform.system()
    try:
        if system == "Windows":
            import ctypes
            label = ctypes.create_unicode_buffer(256)
            ctypes.windll.kernel32.GetVolumeInformationW(  # type: ignore[attr-defined]
                mount_point, label, 256, None, None, None, None, 0,
            )
            return label.value or ""
        elif system == "Darwin":
            result = subprocess.run(
                ["diskutil", "info", mount_point],
                capture_output=True, text=True, timeout=5,
            )
            for line in result.stdout.splitlines():
                if "Volume Name" in line:
                    return line.split(":")[-1].strip()
            return ""
        else:
            try:
                real = os.path.realpath(mount_point)
                parent = os.path.basename(os.path.dirname(real))
                label = os.path.basename(real)
                return label or parent or mount_point
            except OSError:
                return ""
    except Exception:
        return ""


def get_drive_uuid(mount_point: str) -> str:
    system = platform.system()
    try:
        if system == "Linux":
            blkid_path = "/sbin/blkid"
            if not os.path.exists(blkid_path):
                blkid_path = "blkid"
            for partition in _get_linux_partitions():
                if partition.get("mountpoint") == mount_point:
                    return partition.get("uuid", "")
            return ""
        elif system == "Darwin":
            result = subprocess.run(
                ["diskutil", "info", mount_point],
                capture_output=True, text=True, timeout=5,
            )
            for line in result.stdout.splitlines():
                if "UUID" in line:
                    return line.split(":")[-1].strip()
            return ""
        else:
            return ""
    except Exception:
        return ""


def _get_linux_partitions() -> list[dict[str, str]]:
    partitions = []
    try:
        result = subprocess.run(
            ["lsblk", "-no", "MOUNTPOINT,UUID", "-r"],
            capture_output=True, text=True, timeout=5,
        )
        for line in result.stdout.splitlines():
            parts = line.strip().split()
            if len(parts) >= 2:
                partitions.append({
                    "mountpoint": parts[0],
                    "uuid": parts[1],
                })
    except Exception:
        pass
    return partitions


def is_removable_drive(mount_point: str) -> bool:
    import psutil

    system = platform.system()
    try:
        for partition in psutil.disk_partitions(all=True):
            if partition.mountpoint == mount_point:
                if system == "Windows":
                    return "removable" in partition.opts.lower() if partition.opts else False
                elif system == "Darwin":
                    return "/Volumes/" in mount_point or "/mnt/" in mount_point
                else:
                    return (
                        "/media/" in mount_point
                        or "/mnt/" in mount_point
                        or "/run/media/" in mount_point
                    )
    except Exception:
        pass
    return False


def open_folder_in_explorer(path: str) -> None:
    system = platform.system()
    try:
        if system == "Windows":
            os.startfile(path)  # type: ignore[attr-defined]
        elif system == "Darwin":
            subprocess.run(["open", path], check=False)
        else:
            subprocess.run(["xdg-open", path], check=False)
    except Exception:
        pass