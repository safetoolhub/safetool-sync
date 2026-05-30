# This file is part of SafeTool Sync, licensed under GPLv3 with
# additional terms. See LICENSE or https://safetoolhub.org for details.
"""SafeTool Sync shared utilities."""
from __future__ import annotations

from utils.format_utils import (  # noqa: F401
    format_size,
    format_number,
    format_file_count,
    format_duration,
    format_speed,
    format_percentage,
)
from utils.i18n import (  # noqa: F401
    SUPPORTED_LANGUAGES,
    DEFAULT_LANGUAGE,
    get_current_language,
    get_supported_languages,
    init_i18n,
    tr,
)
from utils.logger import (  # noqa: F401
    SimpleLogger,
    configure_logging,
    get_logger,
    log_section_header,
    change_logs_directory,
    set_file_logging_disabled,
)
from utils.storage import (  # noqa: F401
    JsonStorageBackend,
    StorageBackend,
)
from utils.settings_manager import (  # noqa: F401
    SettingsManager,
    settings_manager,
)
from utils.platform_utils import (  # noqa: F401
    get_cpu_count,
    get_system_ram_gb,
    get_system_info,
    get_mounted_drives,
    get_drive_label,
    get_drive_uuid,
    is_removable_drive,
    open_folder_in_explorer,
)