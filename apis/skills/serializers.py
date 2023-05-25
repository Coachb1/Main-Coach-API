from rest_framework import serializers

from skills.models import SkillsRating, SkillIndex


class SkillIndexSerializer(serializers.ModelSerializer):
    class Meta:
        model = SkillIndex
        fields = ["display",
                  "name",
                  "description"]


class SkillsDisplaySerializer(serializers.ModelSerializer):
    class Meta:
        model = SkillsRating
        fields = "__all__"
