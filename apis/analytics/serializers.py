from rest_framework import serializers
from analytics.models import Event

class EventSerializer(serializers.ModelSerializer):
    user_id = serializers.UUIDField(required=True, allow_null=True)
    class Meta:
        model = Event
        fields = [
            "id",
            "event_type",
            "feature",
            "metadata",
            "created",
            "user_id",
        ]
        read_only_fields = ["id", "created"]

    def validate_feature(self, value):
        if not value:
            raise serializers.ValidationError("Feature name is required")
        return value
