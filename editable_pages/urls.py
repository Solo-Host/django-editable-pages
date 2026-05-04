from django.urls import include, path
from rest_framework.routers import DefaultRouter

from .api import EditablePageViewSet

router = DefaultRouter()
router.register(r"pages", EditablePageViewSet, basename="pages")

app_name = "editable_pages"

urlpatterns = [
    path("", include(router.urls)),
]
