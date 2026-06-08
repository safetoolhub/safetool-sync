# This file is part of SafeTool Sync, licensed under GPLv3 with
# additional terms. See LICENSE or https://safetoolhub.org for details.
"""Centralized icon manager for SafeTool Sync using QtAwesome MDI6 icons."""
from __future__ import annotations

try:
    import qtawesome as qta
    from PyQt6.QtCore import QSize
    from PyQt6.QtGui import QIcon
    from PyQt6.QtWidgets import QLabel, QPushButton, QToolButton
    _HAS_QT = True
except ImportError:
    qta = None
    QSize = None
    QIcon = None
    QLabel = None
    QPushButton = None
    QToolButton = None
    _HAS_QT = False


class IconManager:
    ICON_MAP = {
        "cog": "mdi6.cog-outline",
        "mdi6.cog": "mdi6.cog-outline",
        "information": "mdi6.information-outline",
        "information-outline": "mdi6.information-outline",
        "mdi6.information-outline": "mdi6.information-outline",
        "folder-open": "mdi6.folder-open-outline",
        "mdi6.folder-open": "mdi6.folder-open-outline",
        "folder-open-outline": "mdi6.folder-open-outline",
        "mdi6.folder-open-outline": "mdi6.folder-open-outline",
        "folder-outline": "mdi6.folder-outline",
        "mdi6.folder-outline": "mdi6.folder-outline",
        "folder": "mdi6.folder",
        "mdi6.folder": "mdi6.folder",
        "folder-upload": "mdi6.folder-upload",
        "mdi6.folder-upload": "mdi6.folder-upload",
        "folder-download": "mdi6.folder-download",
        "mdi6.folder-download": "mdi6.folder-download",
        "close-circle": "mdi6.close-circle-outline",
        "mdi6.folder-outline": "mdi6.folder-outline",
        "folder": "mdi6.folder",
        "mdi6.folder": "mdi6.folder",
        "folder-upload": "mdi6.folder-upload",
        "mdi6.folder-upload": "mdi6.folder-upload",
        "close-circle": "mdi6.close-circle-outline",
        "minus-circle-outline": "mdi6.minus-circle-outline",
        "mdi6.minus-circle-outline": "mdi6.minus-circle-outline",
        "check": "mdi6.check",
        "check-circle": "mdi6.check-circle-outline",
        "check-circle-outline": "mdi6.check-circle-outline",
        "check-decagram": "mdi6.check-decagram-outline",
        "check-decagram-outline": "mdi6.check-decagram-outline",
        "mdi6.check-decagram-outline": "mdi6.check-decagram-outline",
        "plus-circle": "mdi6.plus-circle-outline",
        "plus-circle-outline": "mdi6.plus-circle-outline",
        "mdi6.plus-circle-outline": "mdi6.plus-circle-outline",
        "mdi6.check-circle-outline": "mdi6.check-circle-outline",
        "alert-circle-outline": "mdi6.alert-circle-outline",
        "alert-octagon": "mdi6.alert-octagon-outline",
        "alert-octagon-outline": "mdi6.alert-octagon-outline",
        "mdi6.alert-octagon-outline": "mdi6.alert-octagon-outline",
        "mdi6.alert-circle-outline": "mdi6.alert-circle-outline",
        "arrow-right-bold-box-outline": "mdi6.arrow-right-bold-box-outline",
        "mdi6.arrow-right-bold-box-outline": "mdi6.arrow-right-bold-box-outline",
        "arrow-left": "mdi6.arrow-left",
        "arrow-down": "mdi6.arrow-down",
        "mdi6.arrow-down": "mdi6.arrow-down",
        "chevron-left": "mdi6.chevron-left",
        "mdi6.chevron-left": "mdi6.chevron-left",
        "settings": "mdi6.cog-outline",
        "wifi-off": "mdi6.wifi-off",
        "shield": "mdi6.shield-outline",
        "sync": "mdi6.sync",
        "mdi6.sync": "mdi6.sync",
        "sync-alert": "mdi6.sync-alert",
        "mdi6.sync-alert": "mdi6.sync-alert",
        "folder-sync": "mdi6.folder-sync-outline",
        "content-copy": "mdi6.content-copy",
        "mdi6.content-copy": "mdi6.content-copy",
        "content-save": "mdi6.content-save-outline",
        "mdi6.content-save": "mdi6.content-save-outline",
        "delete-sweep": "mdi6.delete-sweep-outline",
        "shield-check": "mdi6.shield-check-outline",
        "mdi6.shield-check": "mdi6.shield-check-outline",
        "mdi6.mirror": "mdi6.mirror",
        "camera": "mdi6.camera",
        "camera-plus": "mdi6.camera-plus-outline",
        "camera-plus-outline": "mdi6.camera-plus-outline",
        "mdi6.camera-plus-outline": "mdi6.camera-plus-outline",
        "alert-circle": "mdi6.alert-circle-outline",
        "file-document-outline": "mdi6.file-document-outline",
        "mdi6.file-document-outline": "mdi6.file-document-outline",
        "file-compare": "mdi6.file-compare",
        "harddisk": "mdi6.harddisk",
        "mdi6.harddisk": "mdi6.harddisk",
        "check-all": "mdi6.check-all",
        "arrow-right-bold": "mdi6.arrow-right-bold",
        "chevron-right": "mdi6.chevron-right",
        "mdi6.chevron-right": "mdi6.chevron-right",
        "eye-check": "mdi6.eye-check-outline",
        "filter-variant": "mdi6.filter-variant",
        "mdi6.filter-variant": "mdi6.filter-variant",
        "export": "mdi6.export",
        "history": "mdi6.history",
        "bookmark": "mdi6.bookmark-outline",
        "skip-forward": "mdi6.skip-forward",
        "trash-can-outline": "mdi6.trash-can-outline",
        "rename-box": "mdi6.rename-box",
        "usb": "mdi6.usb",
        "sd": "mdi6.sd",
        "memory": "mdi6.memory",
        "chart-bar": "mdi6.chart-bar",
        "file-tree": "mdi6.file-tree-outline",
        "playlist-check": "mdi6.playlist-check",
        "pause": "mdi6.pause",
        "play": "mdi6.play",
        "play-box-outline": "mdi6.play-box-outline",
        "mdi6.play-box-outline": "mdi6.play-box-outline",
        "redo": "mdi6.redo",
        "view-list": "mdi6.view-list-outline",
        "list": "mdi6.view-list-outline",
        "view-tree": "mdi6/view-tree-outline",
        "folder-search": "mdi6.folder-search-outline",
        "shield-check-outline": "mdi6.shield-check-outline",
        "backup-restore": "mdi6.backup-restore",
        "wizard-cap": "mdi6.wizard-cap",
        "cog-play": "mdi6.cog-play-outline",
        "pencil-box-outline": "mdi6.pencil-box-outline",
        "mdi6.pencil-box-outline": "mdi6.pencil-box-outline",
        "pencil-circle": "mdi6.pencil-circle-outline",
        "pencil-circle-outline": "mdi6.pencil-circle-outline",
        "mdi6.pencil-circle-outline": "mdi6.pencil-circle-outline",
        "mdi6.tune": "mdi6.tune",
        "tune-variant": "mdi6.tune-variant",
        "mdi6.tune-variant": "mdi6.tune-variant",
        "magnify": "mdi6.magnify",
        "mdi6.magnify": "mdi6.magnify",
        "database": "mdi6.database-outline",
        "database-outline": "mdi6.database-outline",
        "mdi6.database-outline": "mdi6.database-outline",
        "mdi6.arrow-right-bold": "mdi6.arrow-right-bold",
        "mdi6.swap-horizontal-bold": "mdi6.swap-horizontal-bold",
        "swap-horizontal": "mdi6.swap-horizontal",
        "mdi6.swap-horizontal": "mdi6.swap-horizontal",
        "swap-vertical": "mdi6.swap-vertical",
        "mdi6.swap-vertical": "mdi6.swap-vertical",
        "mdi6.shield-lock": "mdi6.shield-lock-outline",
        "mdi6.swap-horizontal-circle": "mdi6.swap-horizontal-circle-outline",
        "open-in-new": "mdi6.open-in-new",
        "mdi6.open-in-new": "mdi6.open-in-new",
    }

    def __init__(self) -> None:
        self._cache: dict[str, QIcon] = {}

    def get_icon(self, name: str, color: str | None = None,
                 size: int | None = None, scale_factor: float = 1.0):
        if qta is None or QIcon is None:
            return QIcon() if QIcon is not None else None
        if name not in self.ICON_MAP:
            raise ValueError(f"Icon '{name}' not found in ICON_MAP.")
        cache_key = f"{name}_{color}_{size}_{scale_factor}"
        if cache_key in self._cache:
            return self._cache[cache_key]
        opts: dict = {}
        if color:
            opts["color"] = color
        if scale_factor != 1.0:
            opts["scale_factor"] = scale_factor
        icon = qta.icon(self.ICON_MAP[name], **opts)
        self._cache[cache_key] = icon
        return icon

    def set_button_icon(self, button, icon_name: str,
                        color: str | None = None, size: int = 16) -> None:
        if not _HAS_QT or button is None:
            return
        icon = self.get_icon(icon_name, color=color)
        if icon and QIcon is not None:
            button.setIcon(icon)
            button.setIconSize(QSize(size, size))

    def set_label_icon(self, label, icon_name: str,
                       color: str | None = None, size: int = 16) -> None:
        if not _HAS_QT or label is None:
            return
        icon = self.get_icon(icon_name, color=color)
        if icon and QIcon is not None and QSize is not None:
            pixmap = icon.pixmap(QSize(size, size))
            label.setPixmap(pixmap)


icon_manager = IconManager()