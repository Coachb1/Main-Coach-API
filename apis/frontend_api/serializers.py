from rest_framework import serializers


class FrontendAuthSerializer(serializers.Serializer):
    user_id = serializers.CharField()
    report_type = serializers.CharField()
    shortify_url = serializers.BooleanField(default=False)


class FrontendLeaderboardReportSerializer(serializers.Serializer):
    user_id = serializers.CharField()
    report_type = serializers.CharField()
    skills = serializers.ListField(child=serializers.CharField())


class FrontendCandidateReportSerializer(serializers.Serializer):
    user_id = serializers.CharField()
    report_type = serializers.CharField()
    candidate_id = serializers.CharField()


class FrontendInteractionReportSerializer(serializers.Serializer):
    user_id = serializers.CharField()
    report_type = serializers.CharField()
    interaction_id = serializers.CharField()


class FrontendInteractionSessionReportSerializer(serializers.Serializer):
    user_id = serializers.CharField()
    report_type = serializers.CharField()
    session_id = serializers.CharField()
    interaction_id = serializers.CharField()

class IDPSerializer(serializers.Serializer):
    idp_id = serializers.CharField()
    report_type = serializers.CharField()

class AdminReportSerializer(serializers.Serializer):
    email = serializers.CharField()
    report_type = serializers.CharField()


class FrontendSkillsDiscoveryReportSerializer(serializers.Serializer):
    user_id = serializers.CharField()
    report_type = serializers.CharField()
    session_id = serializers.CharField()
    interaction_id = serializers.CharField()

class FrontendAskingGreatQuestionsReportSerializer(serializers.Serializer):
    user_id = serializers.CharField()
    report_type = serializers.CharField()
    test_attempt_session_id = serializers.CharField()
    interaction_id = serializers.CharField()

class FrontendSkillsTrackerReportSerializer(serializers.Serializer):
    user_id = serializers.CharField()
    report_type = serializers.CharField()

class FrontendCoachingSessionReportSerializer(serializers.Serializer):
    user_id = serializers.CharField()
    report_type = serializers.CharField()
    test_attempt_session_id = serializers.CharField()


class FrontendAccessTokenSerializer(serializers.Serializer):
    refresh_token = serializers.CharField()


class FrontendMeetingAnalysisReportSerializer(serializers.Serializer):
    user_id = serializers.CharField()
    report_type = serializers.CharField()
    test_attempt_session_id = serializers.CharField()


# class FrontendLeaderboardSerializer(serializers.Serializer):
#     tenant_id = serializers.CharField()
#     skills_list = serializers.ListField(child=serializers.CharField())


# class FrontendCandidateSerializer(serializers.Serializer):
#     tenant_id = serializers.CharField()

class DynamicDiscussionReportSerializer(serializers.Serializer):
    user_id = serializers.CharField()
    report_type = serializers.CharField()
    test_attempt_session_id = serializers.CharField()
    interaction_id = serializers.CharField()