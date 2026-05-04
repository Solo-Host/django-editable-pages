from django.urls import include, path

urlpatterns = [
    path(
        "content/",
        include(("editable_pages.urls", "editable_pages"), namespace="editable_pages"),
    ),
]
