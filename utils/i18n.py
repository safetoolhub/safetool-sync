# This file is part of SafeTool Sync, licensed under GPLv3 with
# additional terms. See LICENSE or https://safetoolhub.org for details.
"""Re-export from i18n.core for convenient access."""
from __future__ import annotations

from i18n.core import (  # noqa: F401
    SUPPORTED_LANGUAGES,
    DEFAULT_LANGUAGE,
    get_current_language,
    get_supported_languages,
    init_i18n,
    tr,
)