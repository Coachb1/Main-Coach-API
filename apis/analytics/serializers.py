from rest_framework import serializers
from analytics.models import Event

class FeaturePathField(serializers.CharField):
    """Custom field to serialize/deserialize delimited feature_path strings as lists."""
    
    def to_representation(self, value):
        """Convert stored delimited string to list for API response."""
        if not value:
            return []
        return value.split("|")
    
    def to_internal_value(self, data):
        """Accept list from API input and convert to delimited string."""
        if isinstance(data, list):
            return "|".join(str(x) for x in data) if data else ""
        return str(data)


class EventSerializer(serializers.ModelSerializer):
    user_id = serializers.UUIDField(required=True, allow_null=True)
    # custom field: accepts a list from API but stores as delimited string
    # and returns as list in responses
    feature_path = FeaturePathField(required=False, allow_blank=True)

    class Meta:
        model = Event
        fields = [
            "id",
            "event_type",
            "feature",
            "feature_path",
            "metadata",
            "created",
            "user_id",
        ]
        read_only_fields = ["id", "created"]

    def validate_feature(self, value):
        if not value:
            raise serializers.ValidationError("Feature name is required")
        return value

    def validate(self, attrs):
        # ensure consistency between feature and feature_path
        fp = attrs.get("feature_path")
        feat = attrs.get("feature")
        if fp:
            # fp is now a delimited string, split for validation
            fp_list = fp.split("|") if fp else []
            if feat and fp_list and fp_list[-1] != feat:
                raise serializers.ValidationError({
                    "feature": "Must match last element of feature_path",
                })
            # if feature missing we will auto-populate in view/create
        return attrs
