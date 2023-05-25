from django.urls import path, include
from rest_framework import routers

from apis.skills.views import SkillsViewSet
router = routers.SimpleRouter()

router.register("v1/skills", SkillsViewSet, "skills_v1")

urlpatterns = [
    path("", include(router.urls)),
]
