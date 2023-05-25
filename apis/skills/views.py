from django.http import HttpResponse
from django_filters.rest_framework import DjangoFilterBackend
from rest_framework import mixins
from rest_framework.decorators import action
from rest_framework.filters import OrderingFilter
from rest_framework.response import Response

from apis.skills.serializers import SkillsDisplaySerializer
from clients.permissions import IsAuthenticatedClient
from commons.viewset import ApiViewSet
from pdf_generator.helpers import get_participant_report, get_leaderboard_report
from skills.helpers import top_N_leadership_board, get_participant_info, get_top_participant_skills
from skills.models import SkillsRating
from users.models import User


class SkillsViewSet(ApiViewSet,
                    mixins.ListModelMixin,
                    mixins.RetrieveModelMixin):
    queryset = SkillsRating.objects.filter(deleted=0)
    serializer_class = SkillsDisplaySerializer
    permission_classes = (IsAuthenticatedClient,)
    filter_backends = (DjangoFilterBackend, OrderingFilter)
    filterset_fields = ("participant_id",)
    ordering_fields = '__all__'
    lookup_field = "uid"

    def get_queryset(self):
        return super().get_queryset().filter(tenant_id=self.request.tenant.uid)

    @action(methods=["GET"], detail=False, url_path="top-participants")
    def get_top_participants(self, request, *args, **kwargs):
        qs = self.get_queryset()
        skills = request.query_params.get("skills")
        top_participant_skills = get_top_participant_skills(skills=skills, q_set=qs)
        return Response(SkillsDisplaySerializer(top_participant_skills, many=True).data)

    @action(methods=["GET"], detail=False, url_path="leaderboard-report")
    def get_leadership_report_pdf_view(self, request, *args, **kwargs):
        skills = request.query_params.get("skills")
        skills = skills.split(",")
        skills = [skill.strip() for skill in skills]

        report_url = get_leaderboard_report(skills, tenant_id=request.tenant.uid)

        return Response({"report_url": report_url})
