from rest_framework import serializers


class FrontendAuthSerializer(serializers.Serializer):
    user_id = serializers.CharField()
    report_type = serializers.CharField()


class FrontendAccessTokenSerializer(serializers.Serializer):
    refresh_token = serializers.CharField()


# class FrontendLeaderboardSerializer(serializers.Serializer):
#     tenant_id = serializers.CharField()
#     skills_list = serializers.ListField(child=serializers.CharField())


# class FrontendCandidateSerializer(serializers.Serializer):
#     tenant_id = serializers.CharField()
