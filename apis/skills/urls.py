from django.urls import path, include
from rest_framework import routers

from apis.skills.views import SkillsViewSet, get_top_10_participants, get_top_participants_for_a_test, participant_report

router = routers.SimpleRouter()

router.register("v1/skills", SkillsViewSet, "skills_v1")

# urlpatterns = [
#     path("", include(router.urls))
# ]


urlpatterns = [
    path("", include(router.urls)),
    path("rank-leaderboard", get_top_10_participants, name="rank-top-10"),
    path("rank-test", get_top_participants_for_a_test, name="rank-top-for-test"),
    path("participant-report", participant_report, name="participant-report")
]