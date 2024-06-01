from users.models import SignatureBot, BotAttribute, ClientUserInfo, CoachCoacheeRating,CoachCoacheeMentorMenteeProfile, User, UserAttribute, CoachCoacheeConnection
from utilities.models import BotQnA, DirectoryPageInfo



def delete_user_resources(user_uid):
    profiles = CoachCoacheeMentorMenteeProfile.objects.filter(deleted=False,user_id=user_uid)
    for profile in profiles:
        
        # delete connections if user has coachee profile
        connections = CoachCoacheeConnection.objects.filter(deleted=False,coachee_id=profile.uid)
        for connection in connections:
            connection.delete()
            
        # delete connections if user has coach profile
        connections = CoachCoacheeConnection.objects.filter(deleted=False,coach_id=profile.uid)
        for connection in connections:
            connection.delete()
            
        # delete directorypage for this profile
        dir_infos = DirectoryPageInfo.objects.filter(prifile_id=profile.uid)
        for dir_info in dir_infos:
            dir_info.delete()
            
        profile.delete()
    
    # delete bots if user has any
    bots = SignatureBot.objects.filter(deleted=False,user_id=user_uid)
    for bot in bots:
        # delete bot related resources
        bot_attributes = BotAttribute.objects.filter(deleted=False,bot_id=bot.bot_id)
        for bot_attribute in bot_attributes:
            bot_attribute.delete()
            
        bot_qnas = BotQnA.objects.filter(deleted=False,bot_id=bot.bot_id)
        for bot_qna in bot_qnas:
            bot_qna.delete()
            
        
        bot.delete()