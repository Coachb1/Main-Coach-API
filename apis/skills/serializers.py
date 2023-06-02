from rest_framework import serializers

from skills.models import SkillsRating, SkillIndex, CustomRating


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

class CustomRatingDisplaySerializer(serializers.ModelSerializer):
    class Meta:
        model = CustomRating
        fields = "__all__"
