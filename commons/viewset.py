from rest_framework.pagination import PageNumberPagination
from rest_framework.parsers import JSONParser
from rest_framework.permissions import IsAuthenticated, AllowAny
from rest_framework.viewsets import GenericViewSet

from commons.error_handling import custom_exception_handler


class ApiViewSet(GenericViewSet):
    parser_classes = (JSONParser,)
    pagination_class = PageNumberPagination

    def perform_authentication(self, request):
        return

    def get_exception_handler(self):
        """
        Returns the exception handler that this view uses.
        """
        return custom_exception_handler
