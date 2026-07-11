from django.apps import AppConfig

from .tinymce_settings import apply_tinymce_default_config

apply_tinymce_default_config()


class EditablePagesConfig(AppConfig):
    default_auto_field = "django.db.models.BigAutoField"
    name = "editable_pages"
    verbose_name = "Editable Pages"
