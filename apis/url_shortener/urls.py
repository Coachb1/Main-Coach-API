from django.urls import path, include
from rest_framework import routers

from apis.url_shortener.views import UrlShortenerViewSet

router = routers.SimpleRouter()

router.register("v1/url_shortener", UrlShortenerViewSet, "url_shortener_v1")

urlpatterns = [
    path("", include(router.urls))
]
