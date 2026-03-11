from rest_framework import serializers
from analytics.models import Event


class FeaturePathField(serializers.CharField):
    """Accepts a list or pipe-string from the API; always returns a list."""

    def to_representation(self, value):
        if not value:
            return []
        return value.split("|")

    def to_internal_value(self, data):
        if isinstance(data, list):
            return "|".join(str(x) for x in data)
        return str(data)


class TrackEventSerializer(serializers.Serializer):
    """Input-only serializer for the POST /events/ endpoint."""

    user_id = serializers.UUIDField(required=False, allow_null=True)
    event_type = serializers.ChoiceField(choices=[c[0] for c in Event.EVENT_TYPES])
    feature = serializers.CharField(max_length=100, required=False, allow_blank=True)
    feature_path = FeaturePathField(required=False, allow_blank=True)
    metadata = serializers.DictField(required=False, default=dict)

    def validate(self, attrs):
        feature = attrs.get("feature", "")
        fp = attrs.get("feature_path", "")

        # At least one of feature or feature_path must be present
        if not feature and not fp:
            raise serializers.ValidationError(
                "Provide at least one of 'feature' or 'feature_path'."
            )

        # Consistency check: last element of path must match feature if both given
        if feature and fp:
            last = fp.split("|")[-1]
            if last != feature:
                raise serializers.ValidationError(
                    {"feature": "Must match the last segment of 'feature_path'."}
                )

        return attrs


class EventSerializer(serializers.ModelSerializer):
    feature_path = FeaturePathField(required=False, allow_blank=True)

    class Meta:
        model = Event
        fields = ["id", "event_type", "feature", "feature_path", "metadata", "created"]
        read_only_fields = ["id", "created"]
