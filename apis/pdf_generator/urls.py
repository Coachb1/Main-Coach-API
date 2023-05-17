from django.urls import path
from .views import home, card, GetPDF, generate_report

urlpatterns = [
    path("pdf_generator", home, name="home"),
    path("card/<text>/<template_id>", card, name="card"),
    path('get-pdf/<template_id>', GetPDF.as_view(), name='get_pdf'),
    path('test-report/<test_session_id>', generate_report, name='test_report')
]
