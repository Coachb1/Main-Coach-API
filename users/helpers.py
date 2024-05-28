import logging

from django.contrib.auth.hashers import make_password, check_password

from identities.helpers import get_user_via_identity
from tenants.models import Tenant
from users.models import User, ClientUserInfo, CoachCoacheeMentorMenteeProfile, SignatureBot
from users.models import UserAttribute
from users.choices import BotTypeChoice
from web_auth.helpers import create_new_tokens, logout_entity

logger = logging.getLogger(__name__)


def create_user(tenant: Tenant,
                name: str,
                role: str,
                password: str) -> User:
    """This code defines a function called create_user that creates a new user object and associates it with a specific tenant. 
    The function takes in the tenant object, user name, role, and password as inputs and returns the created user object.
    """
    user = User.objects.create(
        tenant_id=tenant.uid,
        name=name,
        role=role,
        password=make_password(password) if password else None
    )

    logger.info("created user for tenant %s", tenant.uid)

    return user


def login_user(tenant: Tenant,
               identity_type: str,
               identity_value: str,
               password: str) -> dict:
    """
    This code defines a function named `login_user` that takes in a `tenant`, `identity_type`, `identity_value`, and `password` as inputs. 
    It uses the `get_user_via_identity` function to retrieve a user based on the provided identity information. 
    If the user is found, it checks if the user is allowed to login and verifies the password. 
    If the user is valid, it calls the `create_new_tokens` function to generate new tokens for the user. 
    The function then returns the generated tokens.
    
    """
    try:
        logger.info(f"******************* login_user :: identity_type: {identity_type},  itentity_value : {identity_value}")
        user = get_user_via_identity(
            tenant=tenant,
            identity_type=identity_type,
            identity_value=identity_value
        )
    except Exception as e:
        logger.exception("!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!! user get failed err: %s", e)
        raise ValueError("invalid credentials")

    if not user.can_login:
        logger.exception("!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!! user cannot login")
        raise ValueError("invalid credentials")

    if not check_password(password, user.password):
        logger.exception(f"!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!! invalid password : {password}")
        raise ValueError("invalid credentials")

    return create_new_tokens(
        entity_type="user",
        entity_identifier_key="uid",
        entity_identifier_value=user.uid
    )


def logout_user(user: User):
    logout_entity(
        entity_type="user",
        entity_identifier_key="uid",
        entity_identifier_value=user.uid
    )


def upsert_user_attributes(user: User, tag: str, attributes: dict) -> UserAttribute:
    """
    Update or insert user attributes in the database.

    Args:
        user (User): The User object representing the user for whom the attributes need to be updated or inserted.
        tag (str): The tag of the attributes.
        attributes (dict): A dictionary containing the attributes to be updated or inserted.

    Returns:
        UserAttribute: The updated or newly created UserAttribute object.
    """
    if not attributes:
        return

    user_attribute, created = UserAttribute.objects.get_or_create(
        tenant_id=user.tenant_id,
        user_id=user.uid,
        tag=tag
    )

    updated_attributes = user_attribute.attributes or {}
    updated_attributes.update(attributes)
    user_attribute.attributes = updated_attributes
    user_attribute.save()
    return user_attribute


def get_user_skills_report_attribute(user: User) -> UserAttribute:
    return UserAttribute.objects.filter(
        deleted=False,
        tenant_id=user.tenant_id,
        user_id=user.uid,
        tag="skills_report"
    ).last()


def get_user_attribute(user: User,
                       tag: str) -> UserAttribute:
    return UserAttribute.objects.filter(
        deleted=False,
        tenant_id=user.tenant_id,
        user_id=user.uid,
        tag=tag
    ).last()



def get_client_info_from_user_detail(tenant_id, email = None, user_uid = None):
    if not email and not user_uid:
        return None
    
    def get_client_from_email(email):
        client = ClientUserInfo.objects.filter(deleted=False,tenant_id=tenant_id,member_emails__contains=email).first()
        return client
    
    if email:
        return get_client_from_email(email)
    
    if user_uid:
        user_email = UserAttribute.objects.get(deleted=False,tenant_id=tenant_id,user_id=user_uid).attributes.get('email',None)
        if not user_email:
            return None
        
        return get_client_from_email(user_email)
    

def update_user_account(tenant_id: str, user_id: str, user_data: dict ={}):

    user = User.objects.get(deleted=False,tenant_id=tenant_id,uid=user_id)

    # updating user data
    updated_fields = []

    if user_data.get('name'):
        user.name = user_data.get('name')
        updated_fields.append('name')

    if user_data.get('role'):
        user.role = user_data.get('role')
        updated_fields.append('role')

    if len(updated_fields) > 0:
        user.save(update_fields=updated_fields)

    updated_fields = []
    # updating user attributes

    user_attribute = UserAttribute.objects.get(user_id=user.uid)

    if user_data.get('email'):
        user_attribute.attributes['email'] = user_data.get('email')
        updated_fields.append('attributes')

    if user_data.get('allow_audio_interactions') is not None:
        user_attribute.allow_audio_interactions = user_data.get('allow_audio_interactions')
        updated_fields.append('allow_audio_interactions')

        # prioritize users actions
        user_attribute.prioritize_user_audio_interaction = True
        updated_fields.append('prioritize_user_audio_interaction')


    if user_data.get('restricted_features'):
        user_attribute.restricted_features = user_data.get('restricted_features')
        updated_fields.append('restricted_features')
    
    if user_data.get('restricted_pages'):
        user_attribute.restricted_pages = user_data.get('restricted_pages')
        updated_fields.append('restricted_pages')

    if len(updated_fields) > 0:
        user_attribute.save(update_fields=updated_fields)

    updated_fields = []

    # updating profile if any
    profile = CoachCoacheeMentorMenteeProfile.objects.filter(deleted=False, user_id= user.uid).last()
    if profile:
        if user_data.get('name'):
            profile.name = user_data.get('name')
            updated_fields.append('name')

        if len(updated_fields) > 0:
            profile.save(update_fields=updated_fields)

    return user



def sync_user_low_high_skills(tenant_id, user_id, low_skill, high_skill):
    try:
        logger.info(f"<<<<<<<<<<< sync_low_high_skills => user_id : {user_id}, skills: {low_skill, high_skill} >>>>>>>>>>>>>>>>>")
        profile = CoachCoacheeMentorMenteeProfile.objects.filter(deleted=False,tenant_id=tenant_id,user_id=user_id).last()
        
        if profile:
            profile.high_rating_characteristics = high_skill
            profile.low_rating_characteristics = low_skill
            profile.save()
        
        feedback_bot = SignatureBot.objects.filter(tenant_id=tenant_id,user_id=user_id,bot_type=BotTypeChoice.feedback_bot).first()
        if feedback_bot:
            skills_data = {"high_skill":high_skill,"low_skill":low_skill}
            
            bot_attributes = feedback_bot.attributes
            bot_attributes['low_high_skills'] = skills_data
            feedback_bot.attributes = bot_attributes
            feedback_bot.save()
            
        return {"synced" : True}
    except Exception as e:
        logger.exception(e)
        return {"synced" : False}