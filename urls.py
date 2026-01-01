from django.http import JsonResponse
from django.urls import include
from django.urls import path
from django.contrib import admin
from django.conf import settings
from django.conf.urls.static import static
from drf_spectacular.views import SpectacularAPIView, SpectacularRedocView, SpectacularSwaggerView


ok = JsonResponse({"ok": True})

urlpatterns = [
    path('ht', lambda x: ok),
    path('', lambda x: ok),
    path('hi', lambda x : JsonResponse({'msg':'Hello'})),
    path("api/", include("apis.urls")),
    path('custom-admin/', admin.site.urls),
    path('admin/clearcache/', include('clearcache.urls')),
    path("api/schema/", SpectacularAPIView.as_view(), name="schema"),
    path("api/docs/swagger/", SpectacularSwaggerView.as_view(url_name="schema")),
    path("api/docs/redoc/", SpectacularRedocView.as_view(url_name="schema")),
]

if not settings.DEBUG:
    urlpatterns = urlpatterns + static(settings.STATIC_URL, document_root=settings.STATIC_ROOT)
