from django.urls import path, include
from rest_framework import routers

from apis.skills.views import SkillsViewSet, get_top_10_participants, get_top_participants_for_a_test

router = routers.SimpleRouter()

router.register("v1/skills", SkillsViewSet, "skills_v1")

# urlpatterns = [
#     path("", include(router.urls))
# ]


urlpatterns = [
    path("rank-leaderboard", get_top_10_participants, name="rank-top-10"),
    path("rank-test", get_top_participants_for_a_test, name="rank-top-for-test"),
]