from django.urls import path, include
from rest_framework import routers

from apis.skills.views import SkillsIndexViewSet
from apis.skills.views import SkillsViewSet
from apis.skills.views import CustomRatingViewSet

router = routers.SimpleRouter()

router.register("v1/skills-index", SkillsIndexViewSet, "skills_index_v1")
router.register("v1/skills", SkillsViewSet, "skills_v1")
router.register("v1/custom-rating", CustomRatingViewSet, "custom_rating_v1")

urlpatterns = [
    path("", include(router.urls)),
]
