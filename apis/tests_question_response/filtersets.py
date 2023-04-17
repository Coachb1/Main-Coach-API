from django_filters import FilterSet, CharFilter


class TestQuestionResponseFilterSet(FilterSet):
    test_attempt_session_id = CharFilter(field_name="test_attempt_session_id")
    question_id = CharFilter(field_name="question_id")
