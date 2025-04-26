from rest_framework import serializers
from tests.models import TestReportConfig
from users.choices import UserRoleChoice
from users.models import User, CoachCoacheeMentorMenteeProfile, SignatureBot,BotAttribute, CoachCoacheeConnection, CoachCoacheeRating, UserAttribute, ClientUserInfo, ReportConfig
from commons.cloudinary import upload_image
from utilities.models import UserIDP, DirectoryPageInfo, CoachCoacheeJoiningPreviledge, LLMMappingTable, GlobalSystemInstructions
from commons.utils import get_bot_engagements
from users.db import get_user_by_id, get_user_display_name
from commons.recommendation import recommend_coach_tfidf, recommend_coach_keyword
import json5 as json

import logging
logger = logging.getLogger(__name__)


class UserAttributesUserContextSerializer(serializers.Serializer):
    tag = serializers.CharField()
    attributes = serializers.JSONField()


class SetupAccountUserContextSerializer(serializers.Serializer):
    name = serializers.CharField()
    role = serializers.ChoiceField(choices=UserRoleChoice)
    password = serializers.CharField(required=False, default=None)
    user_attributes = UserAttributesUserContextSerializer(required=False)


class SetupAccountIdentityContextSerializer(serializers.Serializer):
    identity_type = serializers.CharField()
    value = serializers.CharField()


class SetupAccountSerializer(serializers.Serializer):
    user_context = SetupAccountUserContextSerializer()
    identity_context = SetupAccountIdentityContextSerializer()


class AccountSerializer(serializers.ModelSerializer):
    class Meta:
        model = User
        fields = ["uid", "name", "role", "created", "updated"]

    def to_representation(self, instance):
        data =  super().to_representation(instance)

        user_att = UserAttribute.objects.get(deleted=False, user_id=instance.uid)
        if user_att.attributes.get('email'):
            data['email'] = user_att.attributes.get('email')

        data['user_allow_audio_interactions'] = user_att.allow_audio_interactions
        data['prioritize_user_audio_interaction'] = user_att.prioritize_user_audio_interaction
        data['user_restricted_pages'] = user_att.restricted_pages
        data['user_restricted_features'] = user_att.restricted_features
        data['access_allowed'] = user_att.access_allowed
        data['access_denied'] = user_att.access_denied
        data['preferences'] = user_att.preferences

        try:
            profile = CoachCoacheeMentorMenteeProfile.objects.get(deleted=False,is_approved=True,tenant_id=instance.tenant_id,user_id=instance.uid)

            data['profile_type'] = profile.profile_type
            manual_coach_rec = []
            if len(profile.coach_recommendations.all()) > 0:
                logger.info(f"manual recommendation: {profile.coach_recommendations.first().coach_recommendations.split(',')}")
                manual_coach_rec = profile.coach_recommendations.first().coach_recommendations.split(',')

            if profile.problem_statement:
                problem = {"problem": profile.problem_statement}
                # Query the filtered profiles
                filtered_profiles = CoachCoacheeMentorMenteeProfile.objects.filter(
                    deleted=False,
                    is_approved=True,
                    tenant_id=instance.tenant_id,
                    profile_type__in=['coach','icons_by_ai']
                )

                # Create the dictionary
                coaches_dict = {profile.uid: f"{profile.about} \n {profile.discussion_topic}" for profile in filtered_profiles}
                manual_coach_rec.extend([rec[0] for rec in recommend_coach_keyword(problem,coaches_dict)])
                data['coach_recommendation'] = manual_coach_rec
            else:
                data['coach_recommendation'] = manual_coach_rec
        except Exception as e:
            logger.error(f"Error fetching profile: {e}")
            pass
        
        if user_att.attributes.get('email'):
            client = ClientUserInfo.objects.filter(deleted=False,tenant_id=instance.tenant_id,member_emails__contains=user_att.attributes.get('email')).last()
            if client:
                data['client_allow_audio_interactions'] = client.allow_audio_interactions
                data['send_profile_for_reapproval'] = client.send_profile_for_reapproval
        return data



class CoachCoacheeMentorMenteeProfileSerializer(serializers.ModelSerializer):
    profile_image = serializers.FileField(required=False)
    class Meta:
        model = CoachCoacheeMentorMenteeProfile
        fields = ['uid','tenant_id','profile_type','name', 'email', 'status', 'speciality', 'experience', 'location','profile_image',
                'favourite_simulation_codes', 'about', 'department', 'unique_id', 'user_id', 'bot_ids', 'bot_urls', 'profile_image_url','hard_skill_areas',
                'area_domain','provided_links','low_rating_characteristics','high_rating_characteristics','mentoring_preferences',
                'mentoring_frameworks','dominant_point_of_view','problem_solving_approach','admired_leaders','voice_sample','coaching_for_fitment','coaching_level',
                'coach_same_department',
                'supported_outcome',
                'coaching_style',
                'time_commitment',
                'is_approved',  
                'other_details',
                'mob_number',
                'allow_coachee_to_create_session',
                'is_mentor',
                'qna_for_coach_mentor',
                'significant_challenges_and_solutions',
                'common_phrases_and_expressions',
                "journey_and_background",
                "mentorship_contribution",
                "discussion_topic",
                "optional_file_data",
                "problem_statement",
                "provide_answers_using_emojis",
                "meeting_availability",
                ]

        extra_kwargs = {
            'uid': {'read_only': True},
            'unique_id': {'read_only': True},
            'is_approved': {'read_only': True},
        }

    def create(self, validated_data):
        if validated_data.get('profile_image'):
            validated_data['profile_image_url'] = upload_image(validated_data['profile_image']).get('secure_url')
            validated_data.pop('profile_image')
        return CoachCoacheeMentorMenteeProfile.objects.create(**validated_data)
    
    def to_representation(self, instance):
        res = super().to_representation(instance)
        try:
            
            # user_attributes = UserAttribute.objects.get(user_id=instance.user_id)
            # name = user_attributes.attributes.get('real_name',None)
            # print(f"################# user_attributes: {user_attributes.attributes}")
            # if name is None:
            #     name = user_attributes.attributes.get('username',None)
            # if name is None:
            #     name = user_attributes.attributes.get('name',None)

            # res['name'] = name

            name = get_user_display_name(get_user_by_id(instance.user_id))
            if name:
                res['name'] = name

            if instance.optional_file_data:
                res['optional_file_data'] = json.loads(instance.optional_file_data)

            
        except Exception as e:
            logger.error(f"Error in CoachCoacheeMentorMenteeProfileSerializer: {e}")
            
        return res

class BotAttributeSerializer(serializers.ModelSerializer):
    class Meta:
        model = BotAttribute
        fields = '__all__'


class LLMMappingSerializer(serializers.ModelSerializer):
    class Meta:
        model = LLMMappingTable
        fields = '__all__'

class SignatureBotSerializer(serializers.ModelSerializer):
    class Meta:
        model = SignatureBot
        fields = '__all__'

        
    def to_representation(self, instance):
        res = super().to_representation(instance)
        user = User.objects.get(deleted=False,uid=instance.user_id)
        res['creator_name'] = user.name
        llms = LLMMappingTable.objects.filter(deleted=False,tenant_id=instance.tenant_id,bot_type=instance.bot_type).first()
        if llms:
            res['selected_llms'] = LLMMappingSerializer(llms).data
            
        try:
            system_instruction = GlobalSystemInstructions.objects.filter(deleted=False,tenant_id=instance.tenant_id, resourse_type=instance.bot_type).first()
            logger.info(f"system_instruction: {system_instruction.instruction if system_instruction else None}")
            res['system_instructions'] = system_instruction.instruction
        except Exception as e:
            logger.error(f"Error fetching system_instruction: {e}")
            res['system_instructions'] = None
        # if system_instruction:
            
        return res

class UserIDPSerializers(serializers.ModelSerializer):
    class Meta:
        model = UserIDP
        fields = '__all__'

    def to_representation(self, instance):
        data =  super().to_representation(instance)
        chars_to_remove = '*'

        fields_to_clean = [ 'strengths','weaknesses','opportunities',
                            'threats','key_focus_areas','goals',
                            'priorities','learning_histories',
                            'key_skills','skill_gap_for_development',
                            'leadership_skill_focus_areas','book_recommendations',
                            'course_recommendations','recommended_hbr','recommended_ted_talk',
                            'learning_communities']
        for key in fields_to_clean:
            if key in data:
                print(f"######################## key: {key} value: {data[key]}")
                content = data.get(key,' ')
                if content:
                    data[key] = content.replace(chars_to_remove, '')


        return data

class DirectoryInfoSErializer(serializers.ModelSerializer):
    class Meta:
        model = DirectoryPageInfo
        fields = '__all__'

    def to_representation(self, instance):
        data =  super().to_representation(instance)
        try: 
            user = ""
            profile = ""
            if instance.profile_type == 'knowledge_bot':
                user = get_user_by_id(instance.profile_id)
                profile = CoachCoacheeMentorMenteeProfile.objects.filter(deleted=False,user_id=user.uid).first()
            else:
                profile = CoachCoacheeMentorMenteeProfile.objects.filter(deleted=False,uid=instance.profile_id).first()
                user = get_user_by_id(profile.user_id)

            user_att = UserAttribute.objects.get(deleted=False,user_id=user.uid)
            data['email'] = profile.email if profile else user_att.attributes.get('email')
            data['user_id'] = user.uid
            data['created'] = profile.created if profile else user.created
            data['meeting_availability'] = profile.meeting_availability if profile else None

            if profile and profile.admirer_user_ids:
                data['admirer_ids'] = profile.admirer_user_ids.split(',')
            else:
                data['admirer_ids'] = []

            try:
                ratings = CoachCoacheeRating.objects.filter(deleted=False,tenant_id=user.tenant_id , coach_id=profile.uid)
                total_ratings = len(ratings)
                total_score = sum([rating.rating for rating in ratings])
                if total_ratings == 0:
                    data['rating'] = 0
                    data['total_rating'] = 0
                else:
                    data['rating'] = total_score/total_ratings
                    data['total_rating'] = total_ratings
            except Exception as e:
                data['rating'] = 0
                data['total_rating'] = 0

            try:
                signature_bot = ""
                if instance.profile_type == "knowledge_bot":
                    signature_bot = SignatureBot.objects.get(deleted=False,tenant_id=user.tenant_id,bot_id=instance.custom_user_bot_id)
                else:
                    signature_bot = SignatureBot.objects.get(deleted=False,tenant_id=user.tenant_id,bot_id=instance.avatar_bot_id)
                engagements  = get_bot_engagements(tenant_id=user.tenant_id,bot_id=signature_bot.uid)
                data['total_engagement_with_question_count'] = engagements.get('total_engagement_with_question_count',None)
                data['total_without_question_count'] = engagements.get('total_without_question_count',None)
                data['bot_tag'] = signature_bot.tag
                data['bot_uid'] = signature_bot.uid
                data['bot_type'] = signature_bot.bot_type
            except:
                data['total_engagement_with_question_count'] = None
                data['total_engagement_with_question_count'] = None
                data['bot_tag'] = None
                data['bot_uid'] = None
                data['bot_type'] = None
            
        except Exception as e:
            logger.error(f"Error in DirectoryInfoSErializer: {e}")
            data['admirer_ids'] = []
            data['created'] = ""
            data['total_without_question_count'] = None
            data['total_engagement_with_question_count'] = None
            data['rating'] = 0
            data['total_rating'] = 0
            data['email'] = None
            data['user_id'] = None
            data['bot_uid'] = None
            data['bot_type'] = None

        return data



class CoachCoacheeConnectionSerializer(serializers.ModelSerializer):
    class Meta:
        model = CoachCoacheeConnection
        fields = '__all__'

    def to_representation(self, instance):
        data =  super().to_representation(instance)
        try:
            coach = CoachCoacheeMentorMenteeProfile.objects.get(deleted=False,uid=instance.coach_id)
            coachee = CoachCoacheeMentorMenteeProfile.objects.get(deleted=False,uid=instance.coachee_id)
            data['coach_name'] = coach.name
            data['coach_user_id'] = coach.user_id
            data['coach_email'] = coach.email
            data['coachee_email'] = coachee.email
            data['coachee_user_id'] = coachee.user_id
            data['coachee_name'] = coachee.name
            data['allow_coachee_to_create_session'] = coach.allow_coachee_to_create_session
        except:
            data['coach_name'] = None
            data['coachee_name'] = None
            data['coach_user_id'] = None
            data['coachee_user_id'] = None
            data['coach_email'] = None
            data['coachee_email'] = None

        return data
    


class CoachCoacheeJoiningPreviledgeSerializer(serializers.ModelSerializer):
    class Meta:
        model = CoachCoacheeJoiningPreviledge
        fields = '__all__'

class ReportConfigSerializer(serializers.ModelSerializer):
    class Meta:
        model = ReportConfig
        fields = '__all__'

class clientUserInfoSerializer(serializers.ModelSerializer):
    class Meta:
        model = ClientUserInfo
        fields = '__all__'


    def to_representation(self, instance):
        data = super().to_representation(instance)
        try:
            data['report_config'] = ReportConfigSerializer(instance.report_config).data
        except:
            data['report_config'] = None
        return data



class CoachCoacheeRatingSerializer(serializers.ModelSerializer):
    rating = serializers.DecimalField(max_digits=3, decimal_places=2)
    class Meta:
        model = CoachCoacheeRating
        fields = '__all__'
    
    def to_representation(self, instance):
        # data =  super().to_representation(instance)
        data = {}
        try:
            ratings = CoachCoacheeRating.objects.filter(deleted=False,tenant_id=instance.tenant_id , coach_id=instance.coach_id)
            total_ratings = len(ratings)
            total_score = sum([rating.rating for rating in ratings])
            if total_ratings == 0:
                data['averate_rating'] = 0
                data['total_ratings'] = 0
            else:
                data['average_rating'] = total_score/total_ratings
                data['total_ratings'] = total_ratings
        except Exception as e:
            logger.error(f"Error in CoachCoacheeRatingSerializer: {e}")
            data['averate_rating'] = 0
            data['total_ratings'] = 0
            
        return data

class TestReportConfigSerializer(serializers.ModelSerializer):
    class Meta:
        model = TestReportConfig
        fields = '__all__'