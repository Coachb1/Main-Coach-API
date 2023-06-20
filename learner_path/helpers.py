from tests.models import TestQuestion
import json
from commons.anthropic import anthropic_completion


def get_learner_path(queryset, objective, candidate_type):
    # Ask anthropic for the skills called as ant_skills
    if candidate_type is not None:
        temp_set = queryset.filter(candidate_type=candidate_type)

        if len(temp_set) > 0:
            queryset = temp_set

    all_skills_available = set()
    test_to_skills = {}

    for test in queryset:
        curr_skills_set = set()

        curr_skills_list = TestQuestion.objects.filter(test_id=test.uid).values_list(
            'key_learning_skills', flat=True)

        for curr_skills_str in curr_skills_list:

            if curr_skills_str is None:
                continue

            flag = True

            curr_skills_str = curr_skills_str.split(',')
            curr_skills_str = [skill.strip() for skill in curr_skills_str]

            curr_skills_set.update(curr_skills_str)

        all_skills_available.update(curr_skills_set)
        test_to_skills[test.uid] = curr_skills_set

    ant_skills_list = skills_from_anthropic(
        objective, list(all_skills_available))
    ant_skills_list_set = set(ant_skills_list)

    test_to_intersection = {}

    for test in queryset:
        if test.uid not in test_to_skills:
            continue
        test_to_intersection[test.uid] = len(
            test_to_skills[test.uid].intersection(ant_skills_list_set))

    sorted_test_to_intersection = sorted(
        test_to_intersection.items(), key=lambda x: x[1], reverse=True)

    sorted_test_to_intersection = sorted_test_to_intersection[:min(
        5, len(sorted_test_to_intersection))]

    test_uids = [x[0] for x in sorted_test_to_intersection]

    tests = queryset.filter(uid__in=test_uids)

    return tests


def skills_from_anthropic(objective, skills_list):
    # Ask anthropic for the skills called as ant_skills
    ant_skills_list = []

    prompt = f"""
    We have a candidate in the company and his objective is: {objective}. Please recommend what skills he should improve/learn from the list:
    "{skills_list}".

    NOTE: Please choose the skills from this list provided above only and keep the character casing as it is.

    Please respond in a JSON format and no other sentece or texts. The response should look like (EXAMPLE):
    {{
    "skills_list": ["skill1", "skill2"]
    }}

    NOTE THAT: the key of the json must be enclosed in double quotes and the skills inside the list must be enclosed in double quotes.
    """

    cnt = 0

    while cnt < 5:
        try:
            anthropic_response = anthropic_completion(
                prompt, max_tokens=2000)

            res = json.loads(anthropic_response)

            ant_skills_list = res['skills_list']
            break

        except Exception as e:
            cnt += 1
            continue

    if len(skills_list) == 0:
        ant_skills_list = ['management', 'communication']

    return ant_skills_list
