from rest_framework import serializers

from documents.choices import DocActionTypeChoice
from documents.models import Document


class DocumentActionsSerializer(serializers.Serializer):
    action = serializers.ChoiceField(choices=DocActionTypeChoice)
    context = serializers.JSONField(allow_null=True)


class DocumentCreateSerializer(serializers.Serializer):
    owner_type = serializers.CharField()
    owner_id = serializers.CharField()
    display_name = serializers.CharField()
    doc_type = serializers.CharField()
    file = serializers.FileField()
    actions_pipeline = DocumentActionsSerializer(required=False, allow_null=True, many=True)


class DocumentViewSerializer(serializers.ModelSerializer):
    class Meta:
        model = Document
        fields = ("uid", "display_name", "doc_type", "content_type", "size", "owner_type", "owner_id",
                  "transcript_details", "doc_status", "created", "updated")
