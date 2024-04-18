from django.contrib import admin
from django.db.models.signals import post_save
from django.dispatch import receiver
from .models import BotAttribute, SignatureBot, ClientUserInfo, CoachCoacheeMentorMenteeProfile,BotAndUserMapping, CoachCoacheeConnection
import json
from utilities.models import DirectoryPageInfo

class CoachCoacheeMentorMenteeProfileAdmin(admin.ModelAdmin):
    list_per_page = 10
    list_display = ('uid','profile_type','name', 'email', 'is_approved',)
    list_filter = ('profile_type','status','department','is_approved')
    search_fields = ('name', 'email', 'unique_id', 'user_id', 'low_rating_characteristics','high_rating_characteristics','mentoring_preferences'
                    ,'voice_sample','coaching_level',
                        'coach_same_department',
                        'coaching_style',
                        'time_commitment',
                        'is_approved',)
    list_editable = ('is_approved',)
    ordering = ('-id',)


class SignatureBotAdmin(admin.ModelAdmin):
    list_per_page = 10
    list_display = ('uid','bot_id','bot_type','is_approved','is_system_bot','is_sample_bot','use_google_context','is_active')
    list_filter = ('is_approved','is_system_bot','is_sample_bot','use_google_context')
    search_fields = ('bot_name','bot_id')
    list_editable = ('is_approved','is_system_bot','is_sample_bot','use_google_context','is_active')
    ordering = ('-id',)

class BotUserMappingAdmin(admin.ModelAdmin):
    list_per_page = 10
    list_display = ('id','bot_id','bot_owner_name','bot_owner_email','bot_owner_mob_number','user_mob_number','user_name','user_email')
    list_filter = ('bot_id','bot_owner_name','bot_owner_email','bot_owner_mob_number')
    search_fields = ('bot_owner_name','bot_id')
    ordering = ('-id',)

class ClientUserInfoAdmin(admin.ModelAdmin):
    list_per_page = 10
    list_display = ('id','client_name','member_emails','member_mob_numbers','avatar_bot_creation','feedback_bot_creation','subject_matter_bot_creation','number_of_conversation_per_month','restricted_ids','demo_ids','accessed_bot_ids','coach_skills','coach_expertise','departments','restricted_pages','restricted_features')
    list_filter = ('client_name',)
    search_fields = ('client_name',)
    list_editable = ('client_name','member_emails','member_mob_numbers','avatar_bot_creation','feedback_bot_creation','subject_matter_bot_creation','number_of_conversation_per_month','restricted_ids','demo_ids','accessed_bot_ids','coach_skills','coach_expertise','departments','restricted_pages','restricted_features')
    ordering = ('-id',)

admin.site.register(CoachCoacheeMentorMenteeProfile, CoachCoacheeMentorMenteeProfileAdmin)
admin.site.register(BotAttribute)
admin.site.register(SignatureBot, SignatureBotAdmin)
admin.site.register(BotAndUserMapping, BotUserMappingAdmin)
admin.site.register(ClientUserInfo,ClientUserInfoAdmin)


@receiver(post_save, sender=CoachCoacheeMentorMenteeProfile)
def sync_profile_and_bot_data(sender, instance, **kwargs):
    if kwargs['created']:
        return
    # try:
    #     directory = DirectoryPageInfo.objects.filter(profile_id=instance.uid).last()
    #     directory.name = instance.name
    #     directory.department = instance.department
    #     directory.description = instance.about
    #     directory.experience = instance.experience
    #     directory.expertise = instance.area_domain

    #     directory.save()

    # except Exception as e:
    #     print(f"Failed to update directory: {e}")


    if instance.profile_type in ['coachee','mentee']:
        return

    try:
        provided_links = json.loads(instance.provided_links)

    except Exception as e:
        provided_links = instance.provided_links

    try:
        qna_for_coach_mentor = json.loads(instance.qna_for_coach_mentor)

    except Exception as e:
        qna_for_coach_mentor = instance.qna_for_coach_mentor
    
    

    bot_ids = instance.bot_ids
    if bot_ids:
        bot_ids = bot_ids.split(',')
        bots = SignatureBot.objects.filter(deleted=False,bot_id__in=bot_ids)
        for bot in bots:
            if bot.bot_type == 'avatar_bot':
                try:
                    additional_data =  {
                        "profile_type": instance.profile_type,
                        "area_domain": instance.area_domain,
                        "experience": instance.experience,
                        "mentoring_preferences": instance.mentoring_preferences,
                        "mentoring_frameworks": instance.mentoring_frameworks,
                        "dominant_point_of_view": instance.dominant_point_of_view,
                        "problem_solving_approach": instance.problem_solving_approach,
                        "admired_leaders": instance.admired_leaders,
                        "profile_description": instance.about,
                        "department": instance.department,
                        "youtube_links": provided_links.get("youtube_links"),
                        "article_links": provided_links.get("article_links"),
                        "voice_sample": instance.voice_sample,
                        "discuss_how_you_helped_others_in_coachMentoring": instance.mentorship_contribution,
                        "allow_coachee_to_create_session": instance.allow_coachee_to_create_session,
                        "significant_challenges_and_solutions": instance.significant_challenges_and_solutions ,
                        "common_phrases_and_expressions": instance.common_phrases_and_expressions,
                        "journey_and_background": instance.journey_and_background,
                        "fitment_answers": [
                            instance.coaching_level,
                            instance.coach_same_department,
                            instance.supported_outcome,
                        ],
                        "coach_qna": qna_for_coach_mentor.get('coach'),
                        "mentor_qna": qna_for_coach_mentor.get('mentor')
                    }
                    

                    print(additional_data)

                    add_data = bot.data['additional_data']
                    # already_extracted_yt_link = add_data.get('youtube_links',[])
                    # already_extracted_article_link = add_data.get('article_links',[])
                    if add_data:
                        print(f'type of add_data: {type(add_data)}')
                        for key, value in additional_data.items():
                            add_data[key] = value
                        bot.data['additional_data'] = add_data
                        bot.save()

                    # media_data = {}
                    # yt_links = [link.strip() for link in provided_links.get('youtube_links',[])]
                    # yt_links_to_be_extracted = []
                    # for yt_link in yt_links:
                    #     if yt_link not in already_extracted_yt_link:
                    #         yt_links_to_be_extracted.append(yt_link)
                    # article_links = [link.strip() for link in provided_links.get('article_links',[])]
                    # article_links_to_be_extracted = []
                    # for yt_link in article_links:
                    #     if yt_link not in already_extracted_article_link:
                    #         article_links_to_be_extracted.append(yt_link)

                    # if len(yt_links_to_be_extracted) > 0:
                    #     media_data['youtube_links'] = yt_links_to_be_extracted
                    # if len(article_links_to_be_extracted) > 0:
                    #     media_data['article_links'] = article_links_to_be_extracted

                    # if media_data:
                    #     url = f"{BACKEND}/api/v1/accounts/create-bot-by-details/"
                    #     data_json = {'bot_id': bot.uid,"media_data": media_data,}
                    #     resp = requests.request(
                    #         'PATCH',
                    #         url,
                    #         headers=headers,
                    #         data=json.dumps(data_json),
                    #     )

                    #     print(resp.json())
                except Exception as e:
                    print(f'failed to update bot {e}')

post_save.connect(sync_profile_and_bot_data, sender=CoachCoacheeMentorMenteeProfile)
