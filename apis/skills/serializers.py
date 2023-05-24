from rest_framework import serializers
from skills.models import SkillsRating


class SkillsDisplaySerializer(serializers.ModelSerializer):

    class Meta:
        model = SkillsRating
        fields = "__all__"

