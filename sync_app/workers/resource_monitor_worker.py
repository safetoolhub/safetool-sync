# This file is part of SafeTool Sync, licensed under GPLv3 with
# additional terms. See LICENSE or https://safetoolhub.org for details.
"""Resource monitor worker — emits system resource updates every 2 seconds."""
from __future__ import annotations

from PyQt6.QtCore import QThread, pyqtSignal

try:
    import psutil
except ImportError:
    psutil = None  # type: ignore[assignment]


class ResourceMonitorWorker(QThread):
    """Background worker that monitors CPU, RAM, disk space, and write speed.

    Emits resource_update signal every 2 seconds with:
    cpu_percent, ram_free_gb, src_free_gb, dst_free_gb, write_speed_mb
    """

    resource_update = pyqtSignal(float, float, float, float, float)
    error = pyqtSignal(str)

    def __init__(
        self,
        source_path: str | None = None,
        dest_path: str | None = None,
        interval_seconds: int = 2,
        parent=None,
    ) -> None:
        super().__init__(parent)
        self._source_path = source_path
        self._dest_path = dest_path
        self._interval = interval_seconds
        self._cancelled = False
        self._last_disk_io: tuple[int, int] | None = None

    def run(self) -> None:
        if psutil is None:
            self.error.emit("psutil not available for resource monitoring")
            return

        while not self._cancelled:
            try:
                cpu_percent = psutil.cpu_percent(interval=None)

                ram = psutil.virtual_memory()
                ram_free_gb = round(ram.available / (1024 ** 3), 1)

                src_free_gb = 0.0
                dst_free_gb = 0.0

                if self._source_path:
                    try:
                        src_usage = psutil.disk_usage(self._source_path)
                        src_free_gb = round(src_usage.free / (1024 ** 3), 1)
                    except Exception:
                        pass

                if self._dest_path:
                    try:
                        dst_usage = psutil.disk_usage(self._dest_path)
                        dst_free_gb = round(dst_usage.free / (1024 ** 3), 1)
                    except Exception:
                        pass

                write_speed_mb = self._compute_write_speed()

                self.resource_update.emit(
                    cpu_percent,
                    ram_free_gb,
                    src_free_gb,
                    dst_free_gb,
                    write_speed_mb,
                )

            except Exception as e:
                if not self._cancelled:
                    self.error.emit(str(e))

            self.msleep(self._interval * 1000)

    def _compute_write_speed(self) -> float:
        """Compute write speed in MB/s from disk I/O counters."""
        if psutil is None:
            return 0.0

        try:
            disk_io = psutil.disk_io_counters()
            if disk_io is None:
                return 0.0

            current_write_bytes = disk_io.write_bytes

            if self._last_disk_io is not None:
                last_write_bytes, last_time = self._last_disk_io
                import time
                current_time = time.time()
                elapsed = current_time - last_time
                if elapsed > 0:
                    speed = (current_write_bytes - last_write_bytes) / elapsed / (1024 ** 2)
                    self._last_disk_io = (current_write_bytes, current_time)
                    return round(max(0.0, speed), 1)

            import time
            self._last_disk_io = (current_write_bytes, time.time())
            return 0.0

        except Exception:
            return 0.0

    def set_paths(self, source_path: str | None, dest_path: str | None) -> None:
        """Update source and destination paths at runtime."""
        self._source_path = source_path
        self._dest_path = dest_path

    def request_cancel(self) -> None:
        self._cancelled = True