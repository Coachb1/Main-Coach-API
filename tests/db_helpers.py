from tests.models import Test

from tests.models import TestQuestion


def get_test_questions_from_test(test: Test) -> list[TestQuestion]:
    return list(TestQuestion.objects.filter(
        test_id=test.uid,
        deleted=0
    ))
