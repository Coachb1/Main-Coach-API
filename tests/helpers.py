import logging

from django.db import transaction
from rest_framework import serializers

from commons.timeit import timeit
from tenants.models import Tenant
from tests.models import Test
from tests.models import TestInvite
from tests.models import TestQuestion
from users.models import User

logger = logging.getLogger(__name__)


@timeit
def create_test(tenant: Tenant,
                creator_id: str,
                title: str,
                description: str,
                interaction_mode: str,
                is_trainer_mode_enabled: bool,
                questions: list) -> tuple[Test, list[TestQuestion]]:
    try:
        creator = User.objects.get(tenant_id=tenant.uid, uid=creator_id, deleted=0)
    except User.DoesNotExist as e:
        logger.exception("failed to create test, creator with id %s does not exist", creator_id)
        raise serializers.ValidationError("invalid creator id")

    with transaction.atomic():
        test = Test.objects.create(
            tenant_id=tenant.uid,
            creator_id=creator.uid,
            title=title,
            description=description,
            interaction_mode=interaction_mode,
            is_trainer_mode_enabled=is_trainer_mode_enabled,
        )

        test_questions = []
        for question in questions:
            test_questions.append(
                TestQuestion.objects.create(
                    tenant_id=tenant.uid,
                    test_id=test.uid,
                    question_type=question.get("question_type"),
                    media_link=question.get("media_link"),
                    question=question.get("question"),
                    subjective_answer=question.get("subjective_answer"),
                    objective_answer=question.get("objective_answer"),
                    mcq_options=question.get("mcq_options"),
                    mcq_answer=question.get("mcq_answer"),
                )
            )

    logger.info("created test for tenant %s", tenant.uid)

    return test, test_questions


@timeit
def create_test_invite(tenant: Tenant,
                       test_id: str,
                       participant_id: str,
                       expires_at: str) -> TestInvite:
    try:
        test = Test.objects.get(tenant_id=tenant.uid, uid=test_id, deleted=0)
    except Test.DoesNotExist as e:
        logger.exception("failed to create invite, test with id %s does not exist", test_id)
        raise serializers.ValidationError("invalid test id")

    try:
        participant = User.objects.get(tenant_id=tenant.uid, uid=participant_id, deleted=0)
    except User.DoesNotExist as e:
        logger.exception("failed to create invite, participant with id %s does not exist", test_id)
        raise serializers.ValidationError("invalid participant id")

    test_invite = TestInvite.objects.create(
        tenant_id=tenant.uid,
        test_id=test_id,
        participant_id=participant_id,
        expires_at=expires_at
    )

    logger.info("created test invite for tenant %s", tenant.uid)

    return test_invite
