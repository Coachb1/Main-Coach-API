from rest_framework import serializers

from users.choices import UserRoleChoice
from users.models import User, CoachCoacheeMentorMenteeProfile, SignatureBot,BotAttribute, CoachCoacheeConnection, CoachCoacheeRating, UserAttribute
from commons.cloudinary import upload_image
from utilities.models import UserIDP, DirectoryPageInfo, CoachCoacheeJoiningPreviledge
from commons.utils import get_bot_engagements

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
                'common_phrases_and_expressions'
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
            user_attributes = UserAttribute.objects.get(user_id=instance.user_id)
            res['name'] = user_attributes.attributes.get('real_name',None)
            print(f"################# user_attributes: {user_attributes.attributes}")
            if res['name'] is None:
                res['name'] = user_attributes.attributes.get('username',None)
        except Exception as e:
            logger.error(f"Error in CoachCoacheeMentorMenteeProfileSerializer: {e}")
            
        return res

class BotAttributeSerializer(serializers.ModelSerializer):
    class Meta:
        model = BotAttribute
        fields = '__all__'

class SignatureBotSerializer(serializers.ModelSerializer):
    class Meta:
        model = SignatureBot
        fields = '__all__'

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
            profile = CoachCoacheeMentorMenteeProfile.objects.get(uid=instance.profile_id)
            data['created'] = profile.created
            if profile.admirer_user_ids:
                data['admirer_ids'] = profile.admirer_user_ids.split(',')
            else:
                data['admirer_ids'] = []

            ratings = CoachCoacheeRating.objects.filter(deleted=False,tenant_id=profile.tenant_id , coach_id=profile.uid)
            total_ratings = len(ratings)
            total_score = sum([rating.rating for rating in ratings])
            if total_ratings == 0:
                data['rating'] = 0
                data['total_rating'] = 0
            else:
                data['rating'] = total_score/total_ratings
                data['total_rating'] = total_ratings

            try:
                signature_bot = SignatureBot.objects.get(deleted=False,tenant_id=profile.tenant_id,bot_id=instance.avatar_bot_id)
                engagements  = get_bot_engagements(tenant_id=profile.tenant_id,bot_id=signature_bot.uid)
                data['total_engagement_with_question_count'] = engagements.get('total_engagement_with_question_count',None)
                data['total_without_question_count'] = engagements.get('total_without_question_count',None)
            except:
                data['total_engagement_with_question_count'] = None
                data['total_engagement_with_question_count'] = None
            
        except Exception as e:
            logger.error(f"Error in DirectoryInfoSErializer: {e}")
            data['admirer_ids'] = []
            data['created'] = ""
            data['total_without_question_count'] = None
            data['total_engagement_with_question_count'] = None
            data['rating'] = 0
            data['total_rating'] = 0

        return data



class CoachCoacheeConnectionSerializer(serializers.ModelSerializer):
    class Meta:
        model = CoachCoacheeConnection
        fields = '__all__'

    def to_representation(self, instance):
        data =  super().to_representation(instance)
        try:
            coach = CoachCoacheeMentorMenteeProfile.objects.get(uid=instance.coach_id)
            coachee = CoachCoacheeMentorMenteeProfile.objects.get(uid=instance.coachee_id)
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