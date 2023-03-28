from django.http import JsonResponse
from django.urls import include
from django.urls import path

ok = JsonResponse({"ok": True})

urlpatterns = [
    path('ht', lambda x: ok),
    path("api/", include("apis.urls"))
]
