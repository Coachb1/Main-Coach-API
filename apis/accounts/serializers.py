from rest_framework import serializers

from users.choices import UserRoleChoice
from users.models import User, CoachCoacheeMentorMenteeProfile, SignatureBot,BotAttribute, CoachCoacheeConnection
from commons.cloudinary import upload_image
from utilities.models import UserIDP, DirectoryPageInfo


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
                'allow_coachee_to_create_session']

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