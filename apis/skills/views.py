import math
from django_filters.rest_framework import DjangoFilterBackend
from rest_framework import mixins, status
from rest_framework.decorators import action
from rest_framework.filters import OrderingFilter
from rest_framework.response import Response
from django.http import HttpResponse

from apis.skills.serializers import SkillIndexSerializer, CreateCustomSkillSerializer
from apis.skills.serializers import SkillsDisplaySerializer, CustomRatingDisplaySerializer
from clients.permissions import IsAuthenticatedClient
from identities.helpers import get_user_via_identity
from identities.models import Identity
from tenants.models import Tenant
from tests.choices import TestAttemptSessionStatusChoices
from tests.models import TestAttemptSession
from users.models import ClientUserInfo, User
from skills.helpers import categorize_skill_scores, evaluate_culture_skills_data_client, evaluate_skills_data_client
from users.permissions import IsAuthenticatedUser
from commons.viewset import ApiViewSet
from pdf_generator.helpers import get_leaderboard_report
from skills.helpers import get_top_participant_skills
from skills.models import SkillIndex
from skills.models import SkillsRating
from skills.models import CustomRating
from skills.helpers import save_the_custom_rating
from skills.constants import skills
from skills.models import CharacteristicsAndPrompts
import logging
logger = logging.getLogger(__name__)

class SkillsIndexViewSet(ApiViewSet,
                         mixins.ListModelMixin,
                         mixins.CreateModelMixin):
    """
    retrive all skill from database
    """
    queryset = SkillIndex.objects.filter(deleted=0)
    serializer_class = SkillIndexSerializer
    permission_classes = (IsAuthenticatedClient,)

    def get_queryset(self):
        return super().get_queryset().filter(tenant_id=self.request.tenant.uid)

class GetSkillsName(ApiViewSet):
    def list(self, request):
        """
        retrive all skill from Skills contants.py
        """
        data = []
        for skill in skills:
            data.append({
                "display": skill['display'],
                "name": skill['name']
            })
        return Response({"data": data})
    

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

        tenant = request.tenant
        data['logo'] = tenant.logo

        return Response({"data": data, "status": "completed"})
    
    @action(methods=["GET"], detail=False, url_path="get-characteristics-list")
    def get_characteristics_list(self, request, *args, **kwargs):
        """
        to retrive characteractics list 
        """
        try:
            characteristics = CharacteristicsAndPrompts.objects.filter(tenant_id = self.request.tenant.uid,deleted=0)
            charac_list = []
            for charac in characteristics:
                charac_list.append(charac.name)
            return Response({"characteristic_list": charac_list }, status=status.HTTP_200_OK)
        except Exception as e:
            return Response({'error': e}, status=status.HTTP_400_BAD_REQUEST)
        
    @action(methods=["GET"], detail=False, url_path="client-skills-list")
    def get_client_skill_info(self, request, *args, **kwargs):
        """
        to retrieve client skills list 
        """
        client = request.query_params.get("client_id")
        tenant_id = self.request.tenant.uid
        try:
            client_users = ClientUserInfo.objects.filter(uid=client, tenant_id=tenant_id, deleted=False).first()
            if not client_users:
                return Response({"error": "Client not found"}, status=status.HTTP_404_NOT_FOUND)
            if not client_users.member_emails:
                return Response({"error": "No users found for this client"}, status=status.HTTP_404_NOT_FOUND)

            result = evaluate_skills_data_client(client_users, tenant_id)

            return Response(result, status=status.HTTP_200_OK)

        except Exception as e:
            return Response({'error': str(e)}, status=status.HTTP_400_BAD_REQUEST)

        
    @action(methods=["GET"], detail=False, url_path="client-cultures-list")
    def get_client_culture_info(self, request, *args, **kwargs):
        """
        to retrive client culture list 
        """
        client = request.query_params.get("client_id")
        tenant_id = self.request.tenant.uid
        try:
            client_users = ClientUserInfo.objects.filter(uid = client, tenant_id = tenant_id, deleted=False).first()
            if not client_users:
                return Response({"error": "Client not found"}, status=status.HTTP_404_NOT_FOUND)
            if not client_users.member_emails:
                return Response({"error": "No users found for this client"}, status=status.HTTP_404_NOT_FOUND)
            
            result = evaluate_culture_skills_data_client(client_users, tenant_id)
            return Response(result, status=status.HTTP_200_OK)
        
        except Exception as e:
            logger.exception("Error in get_client_culture_info: %s", str(e))
            return Response({'error': str(e)}, status=status.HTTP_400_BAD_REQUEST)



class CustomRatingViewSet(ApiViewSet,
                          mixins.ListModelMixin,
                          mixins.RetrieveModelMixin):
    """
    to retrive or create custom rating
    """
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
