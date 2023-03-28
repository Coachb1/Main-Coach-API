from rest_framework import mixins

from apis.tenants.serializers import TenantSerializer
from commons.viewset import ApiViewSet
from tenants.models import Tenant


class TenantViewSet(ApiViewSet,
                    mixins.RetrieveModelMixin,
                    mixins.ListModelMixin,
                    mixins.CreateModelMixin,
                    mixins.UpdateModelMixin):
    queryset = Tenant.objects.filter(deleted=0)
    serializer_class = TenantSerializer
    lookup_field = "uid"
