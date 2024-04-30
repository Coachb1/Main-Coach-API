from tests.models import Test

from tests.models import TestQuestion


def get_test_questions_from_test(test: Test) -> list[TestQuestion]:
    """
    Retrieves a list of TestQuestion objects associated with a given Test object.

    This function filters the TestQuestion objects based on the 'test_id' attribute, which should match the 'uid' attribute of the provided Test object. It also ensures that the 'deleted' attribute of the TestQuestion objects is 0, indicating that these questions are not marked as deleted.

    Args:
        test (Test): A Test object for which associated TestQuestion objects are to be retrieved. The Test object must have a 'uid' attribute.

    Returns:
        list[TestQuestion]: A list of TestQuestion objects that are associated with the provided Test object and are not marked as deleted. If no such TestQuestion objects exist, an empty list is returned.

    Example:
        test = Test.objects.get(uid='some_uid')
        test_questions = get_test_questions_from_test(test)
        # test_questions now contains a list of TestQuestion objects associated with the 'test' object, if any exist.
    """
    return list(TestQuestion.objects.filter(
        test_id=test.uid,
        deleted=0
    ))
