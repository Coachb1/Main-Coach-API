from django.contrib import admin
from django.db.models.signals import post_save
from django.dispatch import receiver
from .models import (BotAttribute, SignatureBot, ClientUserInfo, CoachCoacheeMentorMenteeProfile,BotAndUserMapping, CoachCoacheeConnection
                 ,User,UserAttribute, CoachRecommendationsForUser, ReportConfig, SnippetAccessCode, AccessCodeLog)
import json
from utilities.models import DirectoryPageInfo, BotQnA
from coaching_conversations.helpers import shift_all_emails_to_domain_client
from email_sender.helpers import send_welcome_email
from tenants.admin import TenantAwareModelAdmin
from users.choices import BotTypeChoice
from django import forms
from import_export.admin import ExportActionMixin
from import_export import resources
from users.models import get_unique_access_code

class CoachCoacheeMentorMenteeProfileAdmin(TenantAwareModelAdmin):
    list_per_page = 10
    list_display = ('id','uid','profile_type','name', 'email','use_coachee_info_in_prompt')
    list_filter = ('profile_type','status','department','is_approved')
    search_fields = ('name', 'uid','email', 'unique_id', 'user_id', 'low_rating_characteristics','high_rating_characteristics','mentoring_preferences'
                    ,'voice_sample','coaching_level',
                        'coach_same_department',
                        'coaching_style',
                        'time_commitment',
                        )
    list_editable = ('use_coachee_info_in_prompt',)
    ordering = ('-id',)


class SignatureBotAdmin(TenantAwareModelAdmin):
    list_per_page = 10
    list_display = ('id','uid','bot_id','bot_type','page_informations','is_system_bot','is_sample_bot','use_google_context','use_personality_context','is_active','is_private','allow_public_access','integratable_widget_snippet')
    list_filter = ('is_system_bot','is_sample_bot','use_google_context','bot_type','is_private','allow_public_access')
    search_fields = ('bot_id','bot_type','uid')
    list_editable = ('page_informations','is_system_bot','is_sample_bot','use_google_context','is_active','use_personality_context','is_private','allow_public_access')
    ordering = ('-id',)

class BotUserMappingAdmin(TenantAwareModelAdmin):
    list_per_page = 10
    list_display = ('id','bot_id','bot_owner_name','bot_owner_email','bot_owner_mob_number','user_mob_number','user_name','user_email')
    list_filter = ('bot_id','bot_owner_name','bot_owner_email','bot_owner_mob_number')
    search_fields = ('bot_owner_name','bot_id')
    ordering = ('-id',)

class CoachRecommendationsAdmin(TenantAwareModelAdmin):
    list_per_page = 10
    list_display = ('id','get_user_profile_name','get_user_profile_email','coach_recommendations')
    search_fields = ('user_profile__name','user_profile__email')
    list_editable = ('coach_recommendations',)
    ordering = ('-id',)

    def get_user_profile_name(self, obj):
        return obj.user_profile.name
    get_user_profile_name.admin_order_field = 'user_profile__name'
    get_user_profile_name.short_description = 'User Profile Name'

    def get_user_profile_email(self, obj):
        return obj.user_profile.email
    get_user_profile_email.admin_order_field = 'user_profile__email'
    get_user_profile_email.short_description = 'User Profile Email'

class ClientUserInfoAdmin(TenantAwareModelAdmin):
    list_per_page = 10
    list_display = ('id','uid','client_name','domain_name','widget_access_code','member_emails','email_address_list','restricted_ids','demo_ids','accessed_bot_ids','coach_skills','coach_expertise','departments','restricted_pages','restricted_features','allowed_ips','ui_information','help_text','heading','sub_heading','tag_line','excluded_users','use_skills_from_skill_bank','allow_audio_interactions','make_new_user_in_trail','allow_paste_answer','send_profile_for_reapproval')
    list_filter = ('client_name',)
    search_fields = ('client_name','domain_name','uid')
    list_editable = ('domain_name','member_emails','email_address_list','restricted_ids','demo_ids','accessed_bot_ids','coach_skills','coach_expertise','departments','restricted_pages','restricted_features','allowed_ips','allow_audio_interactions','make_new_user_in_trail','ui_information','help_text','heading','sub_heading','tag_line','excluded_users','allow_paste_answer','use_skills_from_skill_bank','send_profile_for_reapproval')
    ordering = ('-id',)


class SnippetAccessCodeForm(forms.ModelForm):
    generate_more = forms.IntegerField(
        label="Number of access code", 
        min_value=1, 
        initial=1, 
        help_text="Enter the number of access codes to generate with same confirations."
    )

    class Meta:
        model = SnippetAccessCode
        fields = ['client', 'access_code', 'is_active', 'is_temporary', 'max_test_attempts']

    def clean(self):
        if self.cleaned_data['generate_more'] < 1:
            raise forms.ValidationError("Number of access codes to generate must be greater than 0.")
        
        cleaned_data = super().clean()
        num_codes = self.cleaned_data['generate_more']
        if not self.cleaned_data.get('client'):
            raise forms.ValidationError("Please select a client before generating access codes.")
        
        access_codes = []
        if num_codes > 1:
            for _ in range((num_codes-1)):
                access_codes.append(SnippetAccessCode(
                    client=cleaned_data['client'],
                    access_code=get_unique_access_code(
                        SnippetAccessCode, "access_code", cleaned_data['client'].client_name[:3].upper(), length=6
                    ),
                    is_active=cleaned_data['is_active'],  # Default can be adjusted
                    is_temporary=cleaned_data['is_temporary'],  # Adjust if needed
                    max_test_attempts=cleaned_data['max_test_attempts']
                ))
            
            # Bulk create the access codes to reduce database hits
            SnippetAccessCode.objects.bulk_create(access_codes)

        return cleaned_data

class SnippetAccessCodeResource(resources.ModelResource):
    class Meta:
        model = SnippetAccessCode
        fields = ('id', 'client', 'access_code', 'is_active', 'is_temporary', 'max_test_attempts')
        export_order = ('id', 'client', 'access_code', 'is_active', 'is_temporary', 'max_test_attempts')
        

    # Custom field names using dehydrate methods
    def dehydrate_client(self, snippet):
        return snippet.client.client_name

    def dehydrate_is_active(self, snippet):
        return "Active" if snippet.is_active else "Inactive"

    def dehydrate_is_temporary(self, snippet):
        return "Temporary" if snippet.is_temporary else "Permanent"


@admin.register(SnippetAccessCode)
class SnippetAccessCodeAdmin(ExportActionMixin,admin.ModelAdmin):
    form = SnippetAccessCodeForm
    resource_class = SnippetAccessCodeResource
    list_display = ('client', 'access_code', 'is_active', 'is_temporary','max_test_attempts')
    search_fields = ('client__client_name', 'access_code')
    list_filter = ('is_active', 'is_temporary','client__client_name')
    list_editable = ('is_active', 'is_temporary','max_test_attempts')
    ordering = ('-id',)

    def get_export_queryset(self, request):
        queryset = super().get_export_queryset(request)
        return queryset.values('id', 'client__client_name', 'access_code', 'is_active', 'is_temporary', 'max_test_attempts')

@admin.register(AccessCodeLog)
class AccessCodeLogAdmin(admin.ModelAdmin):
    list_display = ('access_code', 'user', 'session_attempted')
    search_fields = ('access_code__access_code', 'user__name')
    list_filter = ('session_attempted',)
    ordering = ('access_code__access_code',)

@admin.register(ReportConfig)
class ReportConfigAdmin(TenantAwareModelAdmin):
    list_display = (
        'id','client', 'skill_rating', 'culture_rating', 'competency_metrix', 'feedback_summary',
        'rating_summary', 'flash_card', 'mindmap', 'speech_metrix', 'powerfiller_words',
        'skill_explanation', 'culture_explanation', 'psychometric_culture_explanation',
        'psychometric_culture_rating'
    )
    list_filter = ('client', 'culture_rating',)  
    search_fields = ('client__client_name',)
    list_editable =  (
        'skill_rating', 'culture_rating', 'competency_metrix', 'feedback_summary',
        'rating_summary', 'flash_card', 'mindmap', 'speech_metrix', 'powerfiller_words',
        'skill_explanation', 'culture_explanation', 'psychometric_culture_explanation',
        'psychometric_culture_rating'
    )
    ordering = ('-id',)



# class UserAdmin(TenantAwareModelAdmin):
#     list_per_page = 10
#     list_display = ('id','tenant_id','name','role','is_root','is_excluded','deleted')
#     list_filter = ('tenant_id','role','is_root','is_excluded')
#     search_fields = ('name',)
#     list_editable = ('name','role','is_root','is_excluded','deleted')
#     ordering = ('-id',)
# class UserAttributesAdmin(TenantAwareModelAdmin):
#     list_per_page = 10
#     list_display = ('id','tenant_id','user_id','attributes','tag','deleted')
#     list_filter = ('tenant_id',)
#     search_fields = ('user_id',)
#     list_editable = ('attributes','deleted')
#     ordering = ('-id',)

admin.site.register(CoachCoacheeMentorMenteeProfile, CoachCoacheeMentorMenteeProfileAdmin)
admin.site.register(BotAttribute)
admin.site.register(SignatureBot, SignatureBotAdmin)
admin.site.register(BotAndUserMapping, BotUserMappingAdmin)
admin.site.register(ClientUserInfo,ClientUserInfoAdmin)
admin.site.register(CoachRecommendationsForUser,CoachRecommendationsAdmin)
# admin.site.register(User,UserAdmin)
# admin.site.register(UserAttribute,UserAttributesAdmin)

@receiver(post_save, sender=ClientUserInfo)
def new_create_client_info_activity(sender, instance, **kwargs):
    if kwargs['created']:
        client_domain = instance.domain_name
        print(f"client_domain: {client_domain}")
        shift_all_emails_to_domain_client(
            tenant_id= instance.tenant_id,
            domain= client_domain
        )

        SnippetAccessCode.objects.create(
            client=instance,
            access_code=instance.widget_access_code,
            is_active=True,
            is_temporary=False
        )

    print(f"================={instance.make_new_user_in_trail}===========")
    if not instance.make_new_user_in_trail and instance.demo_ids != "":
        # remove all ids from demo_ids
        print(f"removed demo_ids")
        instance.demo_ids = ""
        instance.save()


@receiver(post_save, sender=CoachCoacheeMentorMenteeProfile)
def sync_profile_and_bot_data(sender, instance, **kwargs):
    if kwargs['created']:
        print(f"================={instance.profile_type}===========")
        if instance.profile_type in ['coachee','mentee']:
            send_welcome_email(
                profile_type=instance.profile_type,
                user_email=instance.email,
                user_name= instance.name
                )
        return
    try:
        directory = DirectoryPageInfo.objects.filter(profile_id=instance.uid).last()
        updated_fields = []

        if instance.profile_image_url != directory.profile_pic_url:
            directory.profile_pic_url = instance.profile_image_url
            updated_fields.append('profile_pic_url')

        if instance.name != directory.name:
            directory.name = instance.name
            updated_fields.append('name')

        if instance.department != directory.department:
            directory.department = instance.department
            updated_fields.append('department')

        if instance.about != directory.description:
            directory.description = instance.about
            updated_fields.append('description')

        if instance.experience != directory.experience:
            directory.experience = instance.experience
            updated_fields.append('experience')

        if instance.area_domain != directory.expertise:
            directory.expertise = instance.area_domain
            updated_fields.append('expertise')

        if updated_fields:
            directory.save(update_fields=updated_fields)


    except Exception as e:
        print(f"Failed to update directory: {e}")


    fitment_analysis = BotQnA.objects.filter(tenant_id=instance.tenant_id,deleted=False,participant_id=instance.user_id,qna_type='fitment').last()
    if fitment_analysis:
        print(fitment_analysis.participant_qna)
        qna_data = {
            "1": {
                "coach": "What level of coach/mentor do you want to interact with ?",
                "cochee": instance.coaching_level
            },
            "2": {
                "coach": "I want a coach & mentor someone from the same department.",
                "cochee": instance.coach_same_department
            },
            "3": {
                "coach": "What kind of outcome do you want from these sessions the most?",
                "cochee": instance.supported_outcome
            }
        }

        fitment_analysis.participant_qna = qna_data
        fitment_analysis.save(update_fields=['participant_qna'])
    


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
    
    

    bots = SignatureBot.objects.filter(deleted=False,tenant_id=instance.tenant_id,user_id=instance.user_id)

    for bot in bots:
        if bot.bot_type in [BotTypeChoice.avatar_bot, BotTypeChoice.subject_specific_bot]:
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
                    "youtube_links": provided_links.get("youtube_links") if provided_links else None,
                    "article_links": provided_links.get("article_links") if provided_links else None,
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
                    "coach_qna": qna_for_coach_mentor.get('coach') if qna_for_coach_mentor else None,
                    "mentor_qna": qna_for_coach_mentor.get('mentor') if qna_for_coach_mentor else None,
                    "discussion_topic": instance.discussion_topic,
                    "provide_answers_using_emojis": instance.provide_answers_using_emojis
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

                bot.bot_details['coach_name'] = instance.name
                bot.bot_details['info'] = instance.about
                bot.save()

                

                bot_att = BotAttribute.objects.filter(deleted=False, bot_id = bot.uid).last()
                if bot_att:
                    bot_att.about = instance.about
                    bot_att.save()


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
post_save.connect(new_create_client_info_activity, sender=ClientUserInfo)
