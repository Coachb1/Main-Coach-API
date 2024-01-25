from rest_framework import serializers

from users.choices import UserRoleChoice
from users.models import User, CoachCoacheeMentorMenteeProfile, SignatureBot,BotAttribute
from commons.cloudinary import upload_image
from utilities.models import UserIDP


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
        fields = ['uid','profile_type','name', 'email', 'status', 'speciality', 'experience', 'location','profile_image',
                'favourite_simulation_codes', 'about', 'department', 'unique_id', 'user_id', 'bot_ids', 'bot_urls', 'profile_image_url','hard_skill_areas',
                'area_domain','provided_links','low_rating_characteristics','high_rating_characteristics','mentoring_preferences',
                'mentoring_frameworks','dominant_point_of_view','problem_solving_approach','admired_leaders','voice_sample','coaching_for_fitment','coaching_level',
                'coach_same_department',
                'supported_outcome',
                'coaching_style',
                'time_commitment',
                'is_approved',  
                'other_details',
                'mob_number']

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