from django.urls import path
from . import views

urlpatterns = [
    path('test-bulk-upload', views.bulk_test_upload, name='index'),
    path('create-test-web/', views.test_create_web, name='test_create-web'),
    path('create-test-slack/', views.test_create_slack, name='test_create-web'),
    path('test-create-orchestrated-conversation-slack/', views.test_create_orchestrated_conversation_slack, name='test_create_orchestrated_conversation_slack'),
    path('process-file-web/', views.process_web_file, name='process-file-web'),
    path('process-file-slack/', views.process_slack_file, name='process-file-slack'),
    path('process-orchestrated-conversation-file-slack/', views.process_orchestrated_conversation_slack_file, name='process-orchestrated-conversation-slack-file'),
    path('get-power-filler-words/', views.get_filler_and_powerwords, name='get-power-filler-words'),
    path('upload-coach-bots/', views.upload_coach_and_bots, name='upload-coach-bots'),
    path('process-coach-bots/', views.process_coach_and_bots, name='process-coach-bots'),
    path('upload-scenarios/', views.upload_scenarios, name='upload-scenarios'),

]