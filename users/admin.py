from django.contrib import admin
from django.db.models.signals import post_save
from django.dispatch import receiver
from identities.models import Identity
from tenants.models import Tenant
from .models import (BotAttribute, ClientResource, LibraryBotConfig, PortalPageConfig, SignatureBot, ClientUserInfo, CoachCoacheeMentorMenteeProfile,BotAndUserMapping, CoachCoacheeConnection
                 ,User,UserAttribute, CoachRecommendationsForUser, ReportConfig, SnippetAccessCode, AccessCodeLog, UserMindmap)
import json
from utilities.models import DirectoryPageInfo, BotQnA
from coaching_conversations.helpers import enforce_unique_emails_across_clients, shift_all_emails_to_domain_client
from email_sender.helpers import send_welcome_email
from tenants.admin import TenantAwareModelAdmin
from users.choices import BotTypeChoice
from django import forms
from import_export.admin import ExportActionMixin
from import_export import resources
from users.models import get_unique_access_code
from django.urls import path
from django.http import HttpResponseRedirect
from django.shortcuts import render, get_object_or_404
from django.contrib import admin, messages
from .forms import ClientUserInfoForm, LibraryBotConfigForm, TenantForm, ClientForm, UserAdminForm, UserForm
from django.db.models import Q

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

class SignaturebotAttributeAdmin(TenantAwareModelAdmin):
    list_per_page = 10
    list_display = ('id', 'bot_id', 'bot_name', 'about', 'coach_name', 'coach_email', 'client_name', 'is_audio_response')
    list_filter = ('bot_id', 'bot_name', 'coach_name', 'client_name', 'is_audio_response')
    search_fields = ('bot_id', 'bot_name', 'coach_name', 'coach_email', 'client_name')
    list_editable = ('bot_name', 'coach_name', 'coach_email', 'client_name', 'is_audio_response', 'about')
    ordering = ('-id',)

class SignatureBotAdmin(TenantAwareModelAdmin):
    list_per_page = 10
    list_display = ('id','uid','bot_id','bot_type','page_informations','send_bot_transcript','is_system_bot','is_sample_bot','use_google_context','use_personality_context','is_active','is_private','allow_public_access','integratable_widget_snippet')
    list_filter = ('is_system_bot','is_sample_bot','use_google_context','bot_type','is_private','allow_public_access')
    search_fields = ('bot_id','bot_type','uid')
    list_editable = ('page_informations','send_bot_transcript','is_system_bot','is_sample_bot','use_google_context','is_active','use_personality_context','is_private','allow_public_access')
    ordering = ('-id',)

class BotAndUserMappingAdmin(TenantAwareModelAdmin):
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
    
class LibraryBotConfigInline(admin.StackedInline):
    model = LibraryBotConfig
    form = LibraryBotConfigForm
    extra = 1
    can_delete = False
    show_change_link = True
    fieldsets = (
        ("Configuration", {
            "fields": ("bot_config", "show_certification_badge", "default_filters", "feature_and_button_controls", "announcements_section", "feature_boxs", "card_button_config")
        }),
        ("Leaderboard Settings", {
            "fields": ("leaderboard_report_protected", "leaderboard_report_password")
        }),
        ("AI Pulse Settings", {
            "fields": ("ai_pulse_report_protected", "ai_pulse_report_password")
        }),
        ("Ideaboard Settings", {
            "fields": ("ideaboard_report_protected", "ideaboard_report_password")
        }),
        ("Login Settings", {
            "fields": ("login_view", "login_dashboard", "access_password")
        }),
    )

class PortalPageConfigInline(admin.StackedInline):
    model = PortalPageConfig
    extra = 0
    can_delete = True
    show_change_link = True
    fieldsets = (
        ("Configuration", {
            "fields": ("bot_config", "feature_and_button_controls")
        }),
        ("Report Settings", {
            "fields": ("simulation_report_protected", "simulation_report_password")
        }),
    )

@admin.register(ClientResource)
class ClientResourceAdmin(admin.ModelAdmin):
    list_per_page = 10
    list_display = ("name", "label", "clients", "url", "info")
    search_fields = ("name", "url", "label")
    list_editable = ("url", "label", "info")
    ordering = ("-id",)
    fieldsets  = (
        ("Resource Basic", {
            "fields": ("uid", "name")
        }),
        ("Resource Details", {
            "fields": ("label", "url", "info")
        }),
    )

    def clients(self, obj):
        return ", ".join(
            client.client_name for client in obj.client_users.all()
        )

    clients.short_description = "Clients"

class ClientUserInfoAdmin(TenantAwareModelAdmin):
    form = ClientUserInfoForm
    change_list_template = "admin/clientuserinfo/change_list.html"  # custom template for button
    list_per_page = 10
    list_display = ('id','uid','client_name','domain_name', "client_logo", 'widget_access_code','ask_access_code','is_repeat','member_emails','email_address_list','restricted_ids','demo_ids','accessed_bot_ids','coach_skills','coach_expertise','departments','restricted_pages','restricted_features','allowed_ips','ui_information','help_text','heading','sub_heading','tag_line','excluded_users','use_skills_from_skill_bank','allow_audio_interactions','make_new_user_in_trail','allow_paste_answer','send_profile_for_reapproval')
    list_filter = ('client_name',)
    search_fields = ('client_name','domain_name','uid')
    list_editable = ('domain_name', "client_logo", 'is_repeat','member_emails','ask_access_code','email_address_list','restricted_ids','demo_ids','accessed_bot_ids','coach_skills','coach_expertise','departments','restricted_pages','restricted_features','allowed_ips','allow_audio_interactions','make_new_user_in_trail','ui_information','help_text','heading','sub_heading','tag_line','excluded_users','allow_paste_answer','use_skills_from_skill_bank','send_profile_for_reapproval')
    ordering = ('-id',)
    filter_horizontal = ('assigned_tests','assigned_bots', 'collections')
    inlines = [LibraryBotConfigInline, PortalPageConfigInline]

    def get_urls(self):
        urls = super().get_urls()
        custom_urls = [
            path('update-access-control/', self.admin_site.admin_view(self.client_dashboard), name='Update Access control'),
        ]
        return custom_urls + urls
    
    def client_dashboard(self, request):
        context = {
            'title': 'Update Test Per Month / Is Repeat',
        }

        type_ = request.GET.get('type')
        obj_id = request.GET.get('id')
        form = None
        obj = None

        if request.method == "POST":
            type_ = request.POST.get("type")
            obj_id = request.POST.get("object_id")

            if type_ == 'tenant':
                obj = get_object_or_404(Tenant, pk=obj_id)
                form = TenantForm(request.POST, instance=obj)
            elif type_ == 'client':
                obj = get_object_or_404(ClientUserInfo, pk=obj_id)
                form = ClientForm(request.POST, instance=obj)
            elif type_ == 'user':
                obj = get_object_or_404(User, pk=obj_id)
                form = UserForm(request.POST, instance=obj)

            if form and form.is_valid():
                form.save()
                messages.success(request, f"{type_.capitalize()} updated successfully.")
                return HttpResponseRedirect(request.path)

        else:
            if type_ and obj_id:
                if type_ == 'tenant':
                    obj = get_object_or_404(Tenant, pk=obj_id)
                    form = TenantForm(instance=obj)
                elif type_ == 'client':
                    obj = get_object_or_404(ClientUserInfo, pk=obj_id)
                    form = ClientForm(instance=obj)
                elif type_ == 'user':
                    obj = get_object_or_404(User, pk=obj_id)
                    form = UserForm(instance=obj)

        context.update({
            'type': type_,
            'object_id': obj_id,
            'form': form,
            'tenants': Tenant.objects.all(),
            'clients': ClientUserInfo.objects.all(),
            'users': User.objects.all(),
        })

        return render(request, 'admin/clientdashboard.html', context)


# class ClientUserInfoAdmin(TenantAwareModelAdmin):
#     change_list_template = "admin/clientuserinfo/change_list.html"  # Custom template for extra button
#     list_per_page = 10
#     list_display = (
#         'id', 'uid', 'client_name', 'domain_name', 'widget_access_code', 'ask_access_code',
#         'is_repeat', 'member_emails', 'email_address_list', 'restricted_ids', 'demo_ids',
#         'accessed_bot_ids', 'coach_skills', 'coach_expertise', 'departments',
#         'restricted_pages', 'restricted_features', 'allowed_ips', 'ui_information',
#         'help_text', 'heading', 'sub_heading', 'tag_line', 'excluded_users',
#         'use_skills_from_skill_bank', 'allow_audio_interactions', 'make_new_user_in_trail',
#         'allow_paste_answer', 'send_profile_for_reapproval'
#     )
#     list_editable = (
#         'domain_name', 'is_repeat', 'member_emails', 'ask_access_code', 'email_address_list',
#         'restricted_ids', 'demo_ids', 'accessed_bot_ids', 'coach_skills', 'coach_expertise',
#         'departments', 'restricted_pages', 'restricted_features', 'allowed_ips',
#         'allow_audio_interactions', 'make_new_user_in_trail', 'ui_information',
#         'help_text', 'heading', 'sub_heading', 'tag_line', 'excluded_users',
#         'allow_paste_answer', 'use_skills_from_skill_bank', 'send_profile_for_reapproval'
#     )
#     list_filter = ('client_name',)
#     search_fields = ('client_name', 'domain_name', 'uid')
#     ordering = ('-id',)

#     def get_urls(self):
#         urls = super().get_urls()
#         custom_urls = [
#             path('update-access-control/', self.admin_site.admin_view(self.client_dashboard), name='Update Access control'),
#         ]
#         return custom_urls + urls

#     def client_dashboard(self, request):
#         context = {
#             'title': 'Update Test Per Month / Is Repeat',
#         }

#         type_ = request.GET.get('type')
#         obj_id = request.GET.get('id')
#         form = None
#         obj = None

#         if request.method == "POST":
#             type_ = request.POST.get("type")
#             obj_id = request.POST.get("object_id")

#             if type_ == 'tenant':
#                 obj = get_object_or_404(Tenant, pk=obj_id)
#                 form = TenantForm(request.POST, instance=obj)
#             elif type_ == 'client':
#                 obj = get_object_or_404(ClientUserInfo, pk=obj_id)
#                 form = ClientForm(request.POST, instance=obj)
#             elif type_ == 'user':
#                 obj = get_object_or_404(User, pk=obj_id)
#                 form = UserForm(request.POST, instance=obj)

#             if form and form.is_valid():
#                 form.save()
#                 messages.success(request, f"{type_.capitalize()} updated successfully.")
#                 return HttpResponseRedirect(request.path)

#         else:
#             if type_ and obj_id:
#                 if type_ == 'tenant':
#                     obj = get_object_or_404(Tenant, pk=obj_id)
#                     form = TenantForm(instance=obj)
#                 elif type_ == 'client':
#                     obj = get_object_or_404(ClientUserInfo, pk=obj_id)
#                     form = ClientForm(instance=obj)
#                 elif type_ == 'user':
#                     obj = get_object_or_404(User, pk=obj_id)
#                     form = UserForm(instance=obj)

#         context.update({
#             'type': type_,
#             'object_id': obj_id,
#             'form': form,
#             'tenants': Tenant.objects.all(),
#             'clients': ClientUserInfo.objects.all(),
#             'users': User.objects.all(),
#         })

#         return render(request, 'admin/clientdashboard.html', context)


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

@admin.register(UserMindmap)
class UserMindmapAdmin(TenantAwareModelAdmin):
    list_display = ('id','user', 'mindmap_links')
    search_fields = ('user__username', 'mindmap_links')
    list_editable = ('mindmap_links',)

    autocomplete_fields = ['user']

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
class SnippetAccessCodeLogAdmin(admin.ModelAdmin):
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



# -----------------------------
# USER ADMIN
# -----------------------------
@admin.register(User)
class UserAdmin(admin.ModelAdmin):
    form = UserAdminForm

    list_display = (
        "uid",
        "name",
        "role",
        "email_display",
        "client_display",
        "tenant_id",
        "is_active",
        "is_root",
        "attribute_tag",
        "identity_value",
    )

    list_filter = ("role", "is_root", "is_excluded", "tenant_id")
    search_fields = ("name", "uid")
    list_per_page = 10

    def email_display(self, obj):
        return obj.get_email() or "-"
    email_display.short_description = "Email"

    def client_display(self, obj):
        try:
            client = obj.get_client()
        except:
            return "-"
        return client.client_name if client else "-"
    client_display.short_description = "Client"

    # ---------- JSON email search ----------
    def get_search_results(self, request, queryset, search_term):
        queryset, use_distinct = super().get_search_results(request, queryset, search_term)

        if "@" in search_term:
            # JSON search in attributes
            user_ids = [
                a.user_id
                for a in UserAttribute.objects.filter(attributes__email__icontains=search_term)
            ]
            queryset |= User.objects.filter(uid__in=user_ids)

        return queryset, use_distinct

    # ---------- display helpers ----------
    def attribute_tag(self, obj):
        ua = UserAttribute.objects.filter(user_id=obj.uid, deleted=False).first()
        return ua.tag if ua else None
    attribute_tag.short_description = "Attribute Tag"

    def identity_value(self, obj):
        identity = Identity.objects.filter(user_id=obj.uid, deleted=False).first()
        return identity.value if identity else "-"
    identity_value.short_description = "Identity"

    


# class UserAdmin(TenantAwareModelAdmin):
#     # form = UserAdminForm
#     list_per_page = 10
#     list_display = ('id','tenant_id','name','email_display', 'client_display', 'role','is_root','is_excluded','is_repeat','deleted')
#     list_filter = ('tenant_id','role','is_root','is_excluded')
#     search_fields = ('name',)
#     list_editable = ('name','role','is_root','is_excluded','is_repeat','deleted')
#     ordering = ('-id',)

#     # ADVANCED SEARCH
#     def get_search_results(self, request, queryset, search_term):
#         queryset, use_distinct = super().get_search_results(request, queryset, search_term)

#         if search_term:
#             queryset = queryset.filter(
#                 Q(userattribute__attributes__email__icontains=search_term) |
#                 Q(userattribute__attributes__mob_number__icontains=search_term) |
#                 Q(clientuserinfo__member_emails__icontains=search_term)
#             ).distinct()

#         return queryset, use_distinct


#     def email_display(self, obj):
#         return obj.get_email()
#     email_display.short_description = "Email"

#     def client_display(self, obj):
#         client = obj.get_client()
#         return client.client_name if client else None
#     client_display.short_description = "Client"


# class UserAttributesAdmin(TenantAwareModelAdmin):
#     list_per_page = 10
#     list_display = ('id','tenant_id','user_id','attributes','tag','deleted')
#     list_filter = ('tenant_id',)
#     search_fields = ('user_id',)
#     list_editable = ('attributes','deleted')
#     ordering = ('-id',)

admin.site.register(CoachCoacheeMentorMenteeProfile, CoachCoacheeMentorMenteeProfileAdmin)
admin.site.register(BotAttribute, SignaturebotAttributeAdmin)
admin.site.register(SignatureBot, SignatureBotAdmin)
admin.site.register(BotAndUserMapping, BotAndUserMappingAdmin)
admin.site.register(ClientUserInfo,ClientUserInfoAdmin)
admin.site.register(CoachRecommendationsForUser,CoachRecommendationsAdmin)
# admin.site.register(User,UserAdmin)
# admin.site.register(UserAttribute,UserAttributesAdmin)

@receiver(post_save, sender=ClientUserInfo)
def new_create_client_info_activity(sender, instance, **kwargs):
    if kwargs['created']:
        client_domain = instance.domain_name
        print(f"client_domain: {client_domain}")
        if client_domain:
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

    enforce_unique_emails_across_clients(instance)       

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
