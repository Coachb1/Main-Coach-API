from django_filters.rest_framework import DjangoFilterBackend
from rest_framework import mixins, status
from rest_framework.decorators import action
from rest_framework.filters import OrderingFilter
from rest_framework.response import Response

from apis.skills.serializers import SkillIndexSerializer, CreateCustomSkillSerializer
from apis.skills.serializers import SkillsDisplaySerializer, CustomRatingDisplaySerializer
from clients.permissions import IsAuthenticatedClient
from users.permissions import IsAuthenticatedUser
from commons.viewset import ApiViewSet
from pdf_generator.helpers import get_leaderboard_report
from skills.helpers import get_top_participant_skills
from skills.models import SkillIndex
from skills.models import SkillsRating
from skills.models import CustomRating
from skills.helpers import save_the_custom_rating


class SkillsIndexViewSet(ApiViewSet,
                         mixins.ListModelMixin):
    queryset = SkillIndex.objects.filter(deleted=0)
    serializer_class = SkillIndexSerializer
    permission_classes = (IsAuthenticatedClient,)

    def get_queryset(self):
        return super().get_queryset().filter(tenant_id=self.request.tenant.uid)


class SkillsViewSet(ApiViewSet,
                    mixins.ListModelMixin,
                    mixins.RetrieveModelMixin):
    queryset = SkillsRating.objects.filter(deleted=0)
    serializer_class = SkillsDisplaySerializer
    permission_classes = (IsAuthenticatedClient, IsAuthenticatedUser)
    filter_backends = (DjangoFilterBackend, OrderingFilter)
    filterset_fields = ("participant_id",)
    ordering_fields = '__all__'
    lookup_field = "uid"

    def get_queryset(self):
        return super().get_queryset().filter(tenant_id=self.request.tenant.uid)

    @action(methods=["GET"], detail=False, url_path="top-participants")
    def get_global_skills(self, request, *args, **kwargs):
        qs = self.get_queryset()
        skills = request.query_params.get("skills")
        top_participant_skills = get_top_participant_skills(
            skills=skills, q_set=qs)
        return Response(SkillsDisplaySerializer(top_participant_skills, many=True).data)

    @action(methods=["GET"], detail=False, url_path="top-participants")
    def get_top_participants(self, request, *args, **kwargs):
        qs = self.get_queryset()
        skills = request.query_params.get("skills")
        top_participant_skills = get_top_participant_skills(
            skills=skills, q_set=qs)
        return Response(SkillsDisplaySerializer(top_participant_skills, many=True).data)

    @action(methods=["GET"], detail=False, url_path="leaderboard-report")
    def get_leadership_report_pdf_view(self, request, *args, **kwargs):
        skills = request.query_params.get("skills")
        skills = skills.split(",")
        skills = [skill.strip() for skill in skills]

        report_url = get_leaderboard_report(
            skills, tenant_id=request.tenant.uid)

        return Response({"report_url": report_url})

    @action(methods=["GET"], detail=False, url_path="leaderboard-report-data")
    def get_leadership_report_frontend(self, request, *args, **kwargs):
        skills = request.query_params.get("skills")
        skills = skills.split(",")
        skills = [skill.strip() for skill in skills]

        data = get_leaderboard_report(
            skills, tenant_id=request.tenant.uid, only_data=True)

        return Response({"data": data, "status": "completed"})


class CustomRatingViewSet(ApiViewSet,
                          mixins.ListModelMixin,
                          mixins.RetrieveModelMixin):
    queryset = CustomRating.objects.filter(deleted=0)
    serializer_class = CustomRatingDisplaySerializer
    permission_classes = (IsAuthenticatedClient,)
    filter_backends = (DjangoFilterBackend, OrderingFilter)
    filterset_fields = ("tenant_id",)
    ordering_fields = '__all__'
    lookup_field = "uid"

    def get_queryset(self):
        return super().get_queryset().filter(tenant_id=self.request.tenant.uid)

    def create(self, request, *args, **kwargs):
        serializer = CreateCustomSkillSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        custom_rating = {
            "1": serializer.validated_data["one"],
            "2": serializer.validated_data["two"],
            "3": serializer.validated_data["three"],
            "4": serializer.validated_data["four"],
            "5": serializer.validated_data["five"],
        }

        custom_rating_object = CustomRating.objects.get_or_create(
            tenant_id=request.tenant.uid,
            deleted=0,
        )[0]

        save_the_custom_rating(custom_rating, custom_rating_object)

        return Response(custom_rating, status=status.HTTP_201_CREATED)
