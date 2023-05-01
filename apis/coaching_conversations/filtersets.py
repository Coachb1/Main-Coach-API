from django_filters import FilterSet, CharFilter


class CoachingConversationFilterSet(FilterSet):
    test_attempt_session_id = CharFilter(field_name="test_attempt_session_id")
