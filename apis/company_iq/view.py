from rest_framework import mixins, status
from rest_framework.decorators import action
from rest_framework.filters import SearchFilter, OrderingFilter
from rest_framework.response import Response
from django_filters.rest_framework import DjangoFilterBackend

from apis.company_iq.serializers import CompanyIQSerializer, ApprovedCompanyIQSerializer
from clients.permissions import IsAuthenticatedClient
from commons.viewset import ApiViewSet
from company_iq.models import CompanyIQ
from drf_spectacular.utils import extend_schema, OpenApiResponse
from drf_spectacular.utils import OpenApiParameter, OpenApiTypes

@extend_schema(
    methods=["GET"],
    summary="List approved CompanyIQ records",
    description=(
        "Retrieve a paginated list of approved CompanyIQ records.\n\n"
        "Supports filtering, searching, and ordering.\n\n"
        "**Filtering:** industry, source\n"
        "**Search:** company, company_normalized, hq\n"
        "**Ordering:** created, revenue_us_millions, employees_full_time"
    ),
    parameters=[
        OpenApiParameter("industry", OpenApiTypes.STR, required=False),
        OpenApiParameter("source", OpenApiTypes.STR, required=False),
        OpenApiParameter("search", OpenApiTypes.STR, required=False, description="Search by company name or HQ"),
        OpenApiParameter("ordering", OpenApiTypes.STR, required=False, description="e.g. created, -revenue_us_millions"),
        OpenApiParameter("page", OpenApiTypes.INT, required=False),
        OpenApiParameter("page_size", OpenApiTypes.INT, required=False),
    ],
    responses={
        200: OpenApiResponse(
            description="List of approved CompanyIQ records",
            response=ApprovedCompanyIQSerializer(many=True),
        ),
        401: OpenApiResponse(description="Unauthorized"),
    },
    tags=["CompanyIQ"],
)
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
    
    @extend_schema(
        methods=["GET"],
        summary="Retrieve CompanyIQ record",
        description="Retrieve a single approved CompanyIQ record by UID.",
        responses={
            200: OpenApiResponse(
                description="CompanyIQ record",
                response=ApprovedCompanyIQSerializer,
            ),
            404: OpenApiResponse(description="Record not found"),
        },
        tags=["CompanyIQ"],
    )
    @extend_schema(
        summary="List all approved CompanyIQ records (internal)",
        description=(
            "Internal endpoint to retrieve all approved CompanyIQ records "
            "without pagination or client filtering.\n\n"
            "Intended for internal services only."
        ),
        responses={
            200: OpenApiResponse(
                description="List of CompanyIQ records",
                response=CompanyIQSerializer(many=True),
            ),
        },
        tags=["CompanyIQ (Internal)"],
    )
    @action(detail=False, methods=["get"], url_path="all")
    def list_all(self, request):
        """
        List all CompanyIQ records, regardless of approval status.
        This is for internal use only.
        """
        queryset = CompanyIQ.objects.filter(deleted=False, approved=True)
        serializer = CompanyIQSerializer(queryset, many=True)
        return Response(serializer.data, status=status.HTTP_200_OK)