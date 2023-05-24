from django.views.generic import View
from django.views import View
from django.http import HttpResponse
from skills.helpers import top_N_leadership_board, top_participants_for_test
from users.models import User
from apis.skills.serializers import SkillsDisplaySerializer

from django_filters.rest_framework import DjangoFilterBackend
from rest_framework.filters import OrderingFilter
from rest_framework import mixins, status
from rest_framework.decorators import action
from rest_framework.response import Response
from skills.models import SkillsRating
from clients.permissions import IsAuthenticatedClient

from commons.viewset import ApiViewSet

def get_top_10_participants(request):

    # get skills from request params
    skills = request.GET.get("skills")
    skills = skills.split(",")
    skills = [skill.strip() for skill in skills]

    participants_skills_scores = top_N_leadership_board(skills, 10)

    # Get users from participant_ids as uid
    participants = []
    for skill_row in participants_skills_scores:
        
        participant = User.objects.get(uid=skill_row.participant_id, tenant_id=skill_row.tenant_id)

        skill_scores = {}

        for skill in skills:
            skill_scores[skill] = getattr(skill_row, f"{skill}_average_score")

        participants.append({
            "name": participant.name,
            "role": participant.role,
            **skill_scores
        })

    return HttpResponse(participants)

def get_top_participants_for_a_test(request):

    # get test_id from request params
    test_id = request.GET.get("test_id")

    participants_sessions = top_participants_for_test(test_id)

    # Get users from participant_ids as uid
    participants = []
    for session in participants_sessions:
        
        participant = User.objects.get(uid=session.participant_id, tenant_id=session.tenant_id)

        participants.append({
            "name": participant.name,
            "role": participant.role,
            "test_score": session.test_score
        })

    return HttpResponse(participants)

class SkillsViewSet(ApiViewSet,
                  mixins.ListModelMixin,
                  mixins.RetrieveModelMixin):
    queryset = SkillsRating.objects.filter(deleted=0)
    serializer_class = SkillsDisplaySerializer
    permission_classes = (IsAuthenticatedClient,)
    filter_backends = (DjangoFilterBackend, OrderingFilter)
    ordering_fields = ("id",)
    lookup_field = "uid"

    def get_queryset(self):
        return super().get_queryset().filter(tenant_id=self.request.tenant.uid)

    

