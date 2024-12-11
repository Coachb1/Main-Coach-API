from users.models import SignatureBot, BotAttribute, ClientUserInfo, CoachCoacheeRating,CoachCoacheeMentorMenteeProfile, User, UserAttribute, CoachCoacheeConnection
from utilities.models import BotQnA, DirectoryPageInfo, SessionNotesRecommendations, UserActionInfo
from tests.models import TestAttemptSession, Test
from coaching_conversations.helpers import add_or_remove_emails_from_client
from identities.models import Identity
from django.db import transaction
from commons.notifications import send_error_notification
from email_sender.helpers import send_email_with_html_template
import logging
import traceback
import datetime
from django.db.models import Q
from users.choices import BotTypeChoice

logger = logging.getLogger(__name__)


def delete_user_resources(user_uid, remove_from_client=False,
                          delete_profile=True,
                          delete_bot =True,
                          delete_user_connections=True,
                          delete_session =True,
                          delete_session_notes=True,
                          delete_user_action = True,
                          soft_delete=False,
                          bot_types = [BotTypeChoice.avatar_bot, BotTypeChoice.subject_specific_bot, BotTypeChoice.user_bot, BotTypeChoice.feedback_bot],
                          bot_ids = None
                          ):
    logger.info("Deleting user resources for user %s", user_uid)
    deleted_list = []
    deleted_msg = ""
    try:
        user = User.objects.get(uid=user_uid)
        tenant_id = user.tenant_id
        connection_uids = []
        profiles = CoachCoacheeMentorMenteeProfile.objects.filter(tenant_id=tenant_id,user_id=user_uid)
        profile_ids = []
        for profile in profiles:
            profile_ids.append(profile.uid)
            

            if delete_user_connections:
                logger.info(f'====================deleting user connections=========================')
                # delete connections if user has coachee profile
                connections = CoachCoacheeConnection.objects.filter(tenant_id=tenant_id,coachee_id=profile.uid)
                for connection in connections:
                    deleted_list.append(f"connection coachee: {connection.uid}")
                    connection_uids.append(connection.uid)
                    connection.delete()
                
                # delete connections if user has coach profile
                connections = CoachCoacheeConnection.objects.filter(tenant_id=tenant_id,coach_id=profile.uid)
                for connection in connections:
                    deleted_list.append(f"connection coach : {connection.uid}")
                    connection_uids.append(connection.uid)
                    connection.delete()

                logger.info(f'====================deleted user connections=========================')
            

            if delete_profile:
                logger.info(f'====================deleting user profile=========================')

                # delete directorypage for this profile
                dir_to_be_deleted = [profile.uid]
                if 'user_bot' in bot_types:
                    dir_to_be_deleted.append(user_uid)

                dir_infos = DirectoryPageInfo.objects.filter(profile_id__in=dir_to_be_deleted)
                for dir_info in dir_infos:
                    deleted_list.append(f"directorypage : {dir_info.name}")
                    dir_info.delete()
                    
                deleted_list.append(f"profile : {profile.uid}")
                if soft_delete:
                    profile.deleted = True
                    profile.save(update_fields=['deleted'])
                else:
                    profile.delete()
        
        # delete bots if user has any
        if delete_bot:
            logger.info(f'====================deleting user bot=========================')
            bots = None
            if bot_ids:
                bots = SignatureBot.objects.filter(tenant_id=tenant_id,uid__in =bot_ids)
            else:
                bots = SignatureBot.objects.filter(tenant_id=tenant_id,user_id=user_uid, bot_type__in=bot_types)
            for bot in bots:
                # delete bot related resources
                bot_attributes = BotAttribute.objects.filter(bot_id=bot.bot_id)
                for bot_attribute in bot_attributes:
                    deleted_list.append(f"bot_attribute : {bot_attribute.uid}")
                    if soft_delete:
                        bot_attribute.deleted = True
                        bot_attribute.save(update_fields=['deleted'])
                    else:
                        bot_attribute.delete()
                    
                bot_qnas = BotQnA.objects.filter(bot_id=bot.bot_id)
                for bot_qna in bot_qnas:
                    deleted_list.append(f"bot_qna_{bot_qna.bot_id} : {bot_qna.uid}")
                    if soft_delete:
                        bot_qna.deleted = True
                        bot_qna.save(update_fields=['deleted'])
                    else:
                        bot_qna.delete()
                    
                deleted_list.append(f"bot : {bot.bot_id}")
                if soft_delete:
                    bot.deleted = True
                    bot.save(update_fields=['deleted'])
                else:
                    bot.delete()

        if user:
            with transaction.atomic():
                if delete_user_action:
                    logger.info(f'====================deleting user action=========================')
                    UserActionInfo.objects.filter(tenant_id=tenant_id, user_id=user.uid).delete()
                if delete_session:
                    logger.info(f'====================deleting user sessions=========================')
                    TestAttemptSession.objects.filter(tenant_id=tenant_id, participant_id=user.uid).update(deleted = True)
                if delete_session_notes:
                    logger.info(f'====================deleting user session notes=========================')
                    SessionNotesRecommendations.objects.filter(
                        tenant_id=tenant_id
                    ).filter(Q(mentee_id=user.uid) | Q(mentor_id=user.uid)).delete()
        
        if remove_from_client:
            logger.info(f'====================removing from client=========================')

            try:
                identity = Identity.objects.get(user_id=user_uid)
                user_email = identity.value
                clients = ClientUserInfo.objects.filter(tenant_id=tenant_id, member_emails__contains=user_email)
                for client in clients:
                    add_or_remove_emails_from_client(client,'member_emails',user_email,True)
                    add_or_remove_emails_from_client(client,'demo_ids',user_email,True)
                    deleted_list.append(f'removed from client : {client.client_name}')
            except Exception as e:
                logger.exception(f"failed to delete client for the user {user_uid}: {e}")


        # checking if all data is deleted:
        profile_ids.append(user_uid)
        deleted_msg += f"""
        
        profile: {CoachCoacheeMentorMenteeProfile.objects.filter(tenant_id=tenant_id,user_id=user_uid).count()}
        connections coach: {CoachCoacheeConnection.objects.filter(tenant_id=tenant_id,coach_id__in=profile_ids).count()}
        connections coachee: {CoachCoacheeConnection.objects.filter(tenant_id=tenant_id,coachee_id__in=profile_ids).count()}
        directorypage: {DirectoryPageInfo.objects.filter(profile_id__in=profile_ids).count()}
        bot: {SignatureBot.objects.filter(tenant_id=tenant_id,user_id=user_uid).count()}
        user_action_info: {UserActionInfo.objects.filter(tenant_id=tenant_id, user_id=user.uid).count()}
        test_attempt_session: {TestAttemptSession.objects.filter(tenant_id=tenant_id, deleted=False, participant_id=user.uid).count()}
        session_notes_recommendations_mentee: {SessionNotesRecommendations.objects.filter(tenant_id=tenant_id, mentee_id=user.uid).count()}
        session_notes_recommendations_mentor: {SessionNotesRecommendations.objects.filter(tenant_id=tenant_id, mentor_id=user.uid).count()}
        """
        if remove_from_client:
            deleted_msg += f"clients: {ClientUserInfo.objects.filter(tenant_id=tenant_id, member_emails__contains=user_email).count()}"


        logger.info(f"delete_list : {deleted_list}, deleted_msg: {deleted_msg}")
        content = f"User: {user.name}- ({user.uid}) \n at => " + datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S") + "\n" + "*"*20 + "User resources deleted." + "*"*20 + "<br/><br/>"
        content += "deleted check: " + deleted_msg + "\n" 
        send_email_with_html_template("User Resource Deletion",content)
    except Exception as e:
        logger.error({"Error":e}, exc_info=True)
        error = f"Got Error: {e}"
        error += "\n traceback: " + traceback.format_exc()
        send_error_notification("delete user resources after client change" if not remove_from_client else "delete user resources from collab", error,{'user_uid':user_uid,'deleted_list': deleted_list,"deleted_confirmation": deleted_msg})
        raise e
