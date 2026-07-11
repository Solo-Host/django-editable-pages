from __future__ import annotations

import sys
from collections.abc import Mapping
from copy import deepcopy
from typing import Any, cast

from django.conf import settings

TINYMCE_DEFAULT_CONFIG: dict[str, Any] = {
    "height": 400,
    "width": "100%",
    "menubar": "file edit view insert format tools table help",
    "plugins": (
        "advlist autolink lists link image charmap preview anchor searchreplace "
        "visualblocks code fullscreen insertdatetime media table help wordcount "
        "template codesample nonbreaking pagebreak save emoticons"
    ),
    "toolbar": (
        "undo redo | bold italic underline strikethrough | "
        "fontfamily fontsize blocks | alignleft aligncenter "
        "alignright alignjustify | outdent indent | numlist bullist | "
        "forecolor backcolor removeformat | pagebreak | charmap emoticons | "
        "fullscreen preview save | image media template link anchor "
        "codesample | code"
    ),
    "custom_undo_redo_levels": 10,
    "language": "en",
    "directionality": "ltr",
    "content_css": [],
    "content_style": (
        "body { font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, "
        "Oxygen, Ubuntu, Cantarell, sans-serif; font-size: 14px }"
    ),
    "valid_elements": "*[*]",
    "extended_valid_elements": (
        "i[class],div[class|style|id],span[class|style],section[id|class|style],"
        "nav[class],ul[class],li[class],a[class|href|target],button[class|type|data-*],"
        "h1[class|id],h2[class|id],h3[class|id],h4[class|id],h5[class|id],h6[class|id],"
        "p[class],ol[class],hr[class]"
    ),
    "templates": [],
    "relative_urls": False,
    "remove_script_host": False,
    "convert_urls": False,
}


def build_tinymce_default_config(overrides: Mapping[str, Any] | None = None) -> dict[str, Any]:
    config = deepcopy(TINYMCE_DEFAULT_CONFIG)
    if overrides is not None:
        config.update(dict(overrides))
    return config


def apply_tinymce_default_config() -> None:
    if not settings.configured:
        return

    configured = getattr(settings, "TINYMCE_DEFAULT_CONFIG", None)
    if configured is not None and not isinstance(configured, Mapping):
        msg = "TINYMCE_DEFAULT_CONFIG must be a mapping."
        raise TypeError(msg)

    merged = build_tinymce_default_config(configured)
    settings.TINYMCE_DEFAULT_CONFIG = merged

    tinymce_settings_module = sys.modules.get("tinymce.settings")
    if tinymce_settings_module is not None:
        cast(Any, tinymce_settings_module).DEFAULT_CONFIG = deepcopy(merged)
