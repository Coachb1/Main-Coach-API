from django.urls import path
from . import views

urlpatterns = [
    path('test-bulk-upload', views.bulk_test_upload, name='index'),
    path('create-test-web/', views.test_create_web, name='test_create-web'),
    path('create-test-slack/', views.test_create_slack, name='test_create-web'),
    path('process-file-web/', views.process_web_file, name='process-file-web'),
    path('process-file-slack/', views.process_slack_file, name='process-file-slack')
]