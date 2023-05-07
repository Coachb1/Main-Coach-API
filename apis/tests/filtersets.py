from django_filters import FilterSet, CharFilter


class TestFilterSet(FilterSet):
    title = CharFilter(method="filter_title_icontains")
    interaction_mode = CharFilter(field_name="interaction_mode")
    test_type = CharFilter(field_name="test_type")
    test_code = CharFilter(field_name="test_code")

    def filter_title_icontains(self, queryset, name, value):
        return queryset.filter(title__icontains=value)
