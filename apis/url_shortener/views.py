from django.shortcuts import render

# Create your views here.
from django_filters.rest_framework import DjangoFilterBackend
from rest_framework import mixins, status
from rest_framework.filters import OrderingFilter
from rest_framework.response import Response
from rest_framework.decorators import action

from apis.url_shortener.serializers import UrlShortenerSerializer, UrlShortenerCheckSerializer
from clients.permissions import IsAuthenticatedClient
from commons.viewset import ApiViewSet

from url_shortener.helpers import chech_url_exists
from url_shortener.models import UrlShortenerMap


class UrlShortenerViewSet(ApiViewSet,
                          mixins.ListModelMixin,
                          mixins.RetrieveModelMixin,
                          mixins.UpdateModelMixin):
    queryset = UrlShortenerMap.objects.filter(deleted=0)
    serializer_class = UrlShortenerSerializer
    permission_classes = (IsAuthenticatedClient,)
    filter_backends = (DjangoFilterBackend, OrderingFilter)
    ordering_fields = ("id", )
    lookup_field = "uid"

    def get_queryset(self):
        return super().get_queryset().filter(tenant_id=self.request.tenant.uid)

    def create(self, request, *args, **kwargs):
        serializer_class = self.get_serializer_class()
        serializer = serializer_class(data=request.data)
        serializer.is_valid(raise_exception=True)

        long_url_hash = serializer.validated_data["long_url_hash"]
        short_url = serializer.validated_data["short_url"]
        long_url = serializer.validated_data["long_url"]

        url_map = UrlShortenerMap.objects.create(
            tenant_id=request.tenant.uid,
            long_url_hash=long_url_hash,
            short_url=short_url,
            long_url=long_url,
        )

        return Response(data=self.serializer_class(instance=url_map).data,
                        status=status.HTTP_201_CREATED)

    @action(methods=["GET"], detail=False, url_path="exists")
    def check_existence(self, request, *args, **kwargs):
        serializer = UrlShortenerCheckSerializer(data=request.query_params)
        serializer.is_valid(raise_exception=True)

        long_url_hash = serializer.validated_data["long_url_hash"]

        short_url = chech_url_exists(long_url_hash, request.tenant.uid)

        if short_url:
            return Response({"short_url": short_url}, status=status.HTTP_200_OK)
        else:
            return Response({"short_url": None}, status=status.HTTP_404_NOT_FOUND)
