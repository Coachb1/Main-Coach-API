from users.models import SignatureBot, BotAttribute, ClientUserInfo, CoachCoacheeRating,CoachCoacheeMentorMenteeProfile, User, UserAttribute, CoachCoacheeConnection
from utilities.models import BotQnA, DirectoryPageInfo, SessionNotesRecommendations, UserActionInfo
from tests.models import TestAttemptSession, Test
from coaching_conversations.helpers import add_or_remove_emails_from_client
from identities.models import Identity
from django.db import transaction
import logging

logger = logging.getLogger(__name__)


def delete_user_resources(user_uid):
    logger.info("Deleting user resources for user %s", user_uid)
    user = User.objects.get(uid=user_uid)
    tenant_id = user.tenant_id
    profiles = CoachCoacheeMentorMenteeProfile.objects.filter(tenant_id=tenant_id,user_id=user_uid)
    for profile in profiles:
        
        # delete connections if user has coachee profile
        connections = CoachCoacheeConnection.objects.filter(tenant_id=tenant_id,coachee_id=profile.uid)
        for connection in connections:
            connection.delete()
            
        # delete connections if user has coach profile
        connections = CoachCoacheeConnection.objects.filter(tenant_id=tenant_id,coach_id=profile.uid)
        for connection in connections:
            connection.delete()
            
        # delete directorypage for this profile
        dir_infos = DirectoryPageInfo.objects.filter(profile_id__in=[profile.uid, user_uid])
        for dir_info in dir_infos:
            dir_info.delete()
            
        profile.delete()
    
    # delete bots if user has any
    bots = SignatureBot.objects.filter(tenant_id=tenant_id,user_id=user_uid)
    for bot in bots:
        # delete bot related resources
        bot_attributes = BotAttribute.objects.filter(bot_id=bot.bot_id)
        for bot_attribute in bot_attributes:
            bot_attribute.delete()
            
        bot_qnas = BotQnA.objects.filter(bot_id=bot.bot_id)
        for bot_qna in bot_qnas:
            bot_qna.delete()
            
        
        bot.delete()

    with transaction.atomic():
        UserActionInfo.objects.filter(tenant_id=tenant_id, user_id=user_uid).delete()
        TestAttemptSession.objects.filter(tenant_id=tenant_id, participant_id=user_uid).update(deleted=True)
        SessionNotesRecommendations.objects.filter(tenant_id=tenant_id, mentee_id=user_uid).delete() 
        SessionNotesRecommendations.objects.filter(tenant_id=tenant_id, mentor_id=user_uid).delete()  
        Test.objects.filter(tenant_id=tenant_id, creator_user_id=user_uid).update(deleted=True)
        Test.objects.filter(tenant_id=tenant_id, assigned_to=user_uid).update(deleted=True)


