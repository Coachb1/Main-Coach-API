from django.http import JsonResponse
from django.urls import include
from django.urls import path
from django.contrib import admin
from django.conf import settings
from django.conf.urls.static import static

from apis.analytics.view import docs_page


ok = JsonResponse({"ok": True})

urlpatterns = [
    path('ht', lambda x: ok),
    path('', lambda x: ok),
    path('hi', lambda x : JsonResponse({'msg':'Hello'})),
    path("api/", include("apis.urls")),
    path('custom-admin/', admin.site.urls),
    path('admin/clearcache/', include('clearcache.urls')),
    path("docs/", docs_page, name="docs"),
    path("client-api/", include("client_apis.apis.urls")),
]

if not settings.DEBUG:
    urlpatterns = urlpatterns + static(settings.STATIC_URL, document_root=settings.STATIC_ROOT)
