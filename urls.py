from django.http import JsonResponse
from django.urls import include
from django.urls import path
from django.contrib import admin
from django.conf import settings
from django.conf.urls.static import static

from bulk_admin_action.utils import create_scenario_view
from bulk_admin_action.views import admin_dashboard, check_task_status, get_csv_view, get_dynamic_csv_view, upload_and_process_llm, upload_view

ok = JsonResponse({"ok": True})

urlpatterns = [
    path('ht', lambda x: ok),
    path('', lambda x: ok),
    path('hi', lambda x : JsonResponse({'msg':'Hello'})),
    path("api/", include("apis.urls")),
    path('custom-admin/', admin.site.urls),
    path('admin/clearcache/', include('clearcache.urls')),
    path('bulk-prompt-runner/', upload_and_process_llm, name='Bulk_Prompt_Runner'),
    path('task-status/<str:task_id>/', check_task_status, name='task_status'),
    path('get-static-test/', get_csv_view, name='get_static_test'),
    path('get-dynamic-test/', get_dynamic_csv_view, name='get_dynamic_test'),
    path('scenario-playground',upload_view,name='upload_view'),
    path('admin-dashboard/', admin_dashboard, name='admin_dashboard'),

    
]

if not settings.DEBUG:
    urlpatterns = urlpatterns + static(settings.STATIC_URL, document_root=settings.STATIC_ROOT)
