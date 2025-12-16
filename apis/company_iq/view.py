from rest_framework import mixins, status
from rest_framework.decorators import action
from rest_framework.filters import SearchFilter, OrderingFilter
from rest_framework.response import Response
from django_filters.rest_framework import DjangoFilterBackend

from apis.company_iq.serializers import CompanyIQSerializer, ApprovedCompanyIQSerializer
from clients.permissions import IsAuthenticatedClient
from commons.viewset import ApiViewSet
from company_iq.models import CompanyIQ


class CompanyIQViewSet(ApiViewSet,
                       mixins.ListModelMixin,
                       mixins.RetrieveModelMixin):
    """
    ViewSet for CompanyIQ records.
    
    Endpoints:
    - GET /v1/company-iq/ - List all approved CompanyIQ records
    - GET /v1/company-iq/{uid}/ - Retrieve a specific CompanyIQ record
    """
    queryset = CompanyIQ.objects.filter(deleted=False, approved=True)
    serializer_class = ApprovedCompanyIQSerializer
    permission_classes = (IsAuthenticatedClient,)
    filter_backends = (DjangoFilterBackend, SearchFilter, OrderingFilter)
    filterset_fields = ("industry", "source")
    search_fields = ("company", "company_normalized", "hq")
    ordering_fields = ("created", "revenue_us_millions", "employees_full_time")
    ordering = ("-created",)
    lookup_field = "uid"

    def get_queryset(self):
        """Override to ensure we only get approved, non-deleted CompanyIQs"""
        return super().get_queryset().filter(deleted=False, approved=True)
