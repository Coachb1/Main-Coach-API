from rest_framework import serializers


class StartSessionSerializer(serializers.Serializer):
    """Input for POST /progress/start/"""
    user_id = serializers.UUIDField()
    case_mapping_id = serializers.UUIDField()


class UpdateProgressSerializer(serializers.Serializer):
    """Input for POST /progress/update/"""
    user_id = serializers.UUIDField()
    case_mapping_id = serializers.UUIDField()
    completion_percentage = serializers.FloatField(min_value=0, max_value=100)


class CompleteSessionSerializer(serializers.Serializer):
    """Input for POST /progress/complete/"""
    user_id = serializers.UUIDField()
    case_mapping_id = serializers.UUIDField()


class ConceptSessionSerializer(serializers.Serializer):
    """
    Output serializer for ConceptSession.

    Uses a plain Serializer (not ModelSerializer) so we don't need to
    import the model at module load time — keeps the analytics app
    decoupled from the tests app.
    """
    uid = serializers.CharField()
    status = serializers.CharField()
    completion_percentage = serializers.FloatField()
    is_active = serializers.BooleanField()
    started_at = serializers.DateTimeField()
    ended_at = serializers.DateTimeField(allow_null=True)
    last_activity_at = serializers.DateTimeField()
    user_uid = serializers.SerializerMethodField()
    case_mapping_uid = serializers.SerializerMethodField()

    def get_user_uid(self, obj):
        return str(obj.user.uid) if obj.user else None

    def get_case_mapping_uid(self, obj):
        return str(obj.case_mapping.uid) if obj.case_mapping else None
