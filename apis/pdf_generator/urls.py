from django.urls import path
from .views import GetPDF, generate_report, get_flash_cards_from_test

urlpatterns = [
    # path("pdf_generator", home, name="home"),
    # path("card/<text>/<template_id>", card, name="card"),
    path('get-pdf/<template_id>', GetPDF.as_view(), name='get_pdf'),
    path('test-report/<test_session_id>', generate_report, name='test_report'),
    path('allinone/<test_id>', get_flash_cards_from_test, name='allinone'),
]
