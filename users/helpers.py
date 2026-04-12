import logging
import secrets
import string

from django.contrib.auth.hashers import make_password, check_password

from apis.accounts.dtos import UserCreateContextDto, IdentityCreateContextDto
from identities.helpers import get_user_via_identity
from tenants.models import Tenant
from users.models import User, ClientUserInfo, CoachCoacheeMentorMenteeProfile, SignatureBot, AccessCodeLog
from users.models import UserAttribute
from users.choices import BotTypeChoice, UserRoleChoice
from web_auth.helpers import create_new_tokens, logout_entity
import random

logger = logging.getLogger(__name__)


def generate_secret_code(length=16):
    """Generate a random alphanumeric secret code for password reset.
    
    Args:
        length (int): Length of the secret code to generate. Default is 16.
    
    Returns:
        str: A random alphanumeric secret code.
    """
    characters = string.ascii_letters + string.digits
    return ''.join(secrets.choice(characters) for _ in range(length))


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

def create_user_acc(tenant: Tenant,
               identity_type: str,
               identity_value: str,
):
    from apis.accounts.aggregator import create_user_account
    user_context = UserCreateContextDto(
        name=identity_value.split("@")[0],
        role=UserRoleChoice.member,
        password="demo@2026",
        user_attributes={
            "tag": "profile",
            "attributes": {"email": identity_value}
        }
    )
    identity_context = IdentityCreateContextDto(
        identity_type=identity_type,
        value=identity_value
    )
    user = create_user_account(tenant, user_context, identity_context)

    return user


def validate_client_access_password(tenant: Tenant,
               password: str,
               client_id: str,
               user:User
               ) -> dict:

    client = user.get_client()

    if not client and client_id:
        try:
            client = ClientUserInfo.objects.get(uid=client_id, tenant_id=tenant.uid, deleted=False)
        except ClientUserInfo.DoesNotExist:
            pass
        
    
    if not client:
        raise ValueError("Invalid credentials")
    


    try:
        if client.library_bot_config.access_password != password:
            raise ValueError("Invalid credentials")
    except Exception:
        raise ValueError("Invalid credentials")



def login_user(tenant: Tenant,
               identity_type: str,
               identity_value: str,
               password: str,
               client_id:str = None) -> dict:
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
    
    new_user = False
    auth_type = "user_login"
    if not user:
        user = create_user_acc(
            tenant=tenant,
            identity_value=identity_value,
            identity_type=identity_type
        )
        user = get_user_via_identity(
            tenant=tenant,
            identity_type=identity_type,
            identity_value=identity_value
        )
        new_user = True

    is_default_password = check_password("demo@2026", user.password)
    if new_user or is_default_password:
        validate_client_access_password(
            tenant=tenant,
            password=password,
            client_id=client_id,
            user=user
        )
        auth_type = 'client_login'

    else:
        if not user.can_login:
            logger.exception("!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!! user cannot login")
            raise ValueError("invalid credentials")

        if not check_password(password, user.password):
            logger.exception(f"!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!! invalid password : {password}")
            raise ValueError("invalid credentials")


    tokens = create_new_tokens(
        entity_type="user",
        entity_identifier_key="uid",
        entity_identifier_value=user.uid
    )

    if auth_type == 'client_login':
        tokens["auth_type"] = auth_type
    
    # Generate and store secret code for new users with client auth
    if new_user:
        secret_code = generate_secret_code()
        user.secret_code = secret_code
        user.save(update_fields=['secret_code'])
        tokens["secret_code"] = secret_code
        logger.info(f"Generated secret code for new user: {user.uid}")

    return tokens


def logout_user(user: User):
    logout_entity(
        entity_type="user",
        entity_identifier_key="uid",
        entity_identifier_value=user.uid
    )


def reset_password_with_secret_code(tenant: Tenant, identity_type:str, identity_value:str ,secret_code: str, new_password: str) -> dict:
    """Reset user password using secret code.
    
    Args:
        tenant (Tenant): Tenant object
        identity_type (str): Identity type
        identity_value (str): Identity value
        secret_code (str): Secret code
        new_password (str): New password
       
    
    Returns:
        dict: Response dictionary with success or error message
    
    Raises:
        ValueError: If user not found or secret code is invalid
    """
    try:
        user = get_user_via_identity(tenant, identity_type, identity_value)
    except Exception as e:
        logger.error(f"User not found")
        raise ValueError("User not found")
    
    # Verify secret code
    secret_codes = [sc.strip() for sc in user.secret_code.split(',') if sc.strip()] if user.secret_code else []
    if secret_code not in secret_codes:
        logger.error(f"Invalid secret code for user")
        raise ValueError("Invalid secret code")
    
    try:
        # Update password
        user.password = make_password(new_password)
        user.save(update_fields=['password'])
        
        logger.info(f"Password reset successfully for user")
        return {"success": "Password reset successfully"}
    except Exception as e:
        logger.exception(f"Error resetting password for user: {e}")
        raise ValueError("Error resetting password")


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
    if tag in ['whatsapp_profile','slack_profile']:

        return UserAttribute.objects.filter(
            deleted=False,
            tenant_id=user.tenant_id,
            user_id=user.uid,
            tag=tag
        ).last()
    else:
        return UserAttribute.objects.filter(
            deleted=False,
            tenant_id=user.tenant_id,
            user_id=user.uid
        ).last()



def get_client_info_from_user_detail(tenant_id, email = None, user_uid = None):
    if not email and not user_uid:
        return None
    
    def get_client_from_email(email):
        try:
            client = ClientUserInfo.objects.filter(deleted=False,tenant_id=tenant_id,member_emails__contains=email).first()
            return client
        except Exception as e:
            logger.exception("get client from email failed: %s", e)
            return None
    
    if email:
        return get_client_from_email(email)
    
    if user_uid:
        try:
            user_email = UserAttribute.objects.get(deleted=False,tenant_id=tenant_id,user_id=user_uid).attributes.get('email',None)
            if not user_email:
                return None
            
            return get_client_from_email(user_email)
        except Exception as e:
            logger.exception("get user email failed: %s", e)
            return None
    

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

    if user_data.get('password'):
        user.password = make_password(user_data.get('password'))
        updated_fields.append('password')

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


    if user_data.get('restricted_features') != None:
        user_attribute.restricted_features = user_data.get('restricted_features')
        updated_fields.append('restricted_features')
    
    if user_data.get('restricted_pages') != None:
        user_attribute.restricted_pages = user_data.get('restricted_pages')
        updated_fields.append('restricted_pages')

    if user_data.get('access_allowed') != None:
        user_attribute.access_allowed = user_data.get('access_allowed')
        updated_fields.append('access_allowed')
    
    if user_data.get('access_denied') != None:
        user_attribute.access_denied = user_data.get('access_denied')
        updated_fields.append('access_denied')

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


def generate_bot_id(bot_type, participant_id, bot_name):
    # Normalize bot name: lowercase, replace spaces with hyphens, remove special characters, and limit to first 4 words
    normalized_bot_name = "-".join(
        bot_name.strip().lower().replace("&", "").replace(" ", "-").split()[:4]
    )

    # Generate the base bot_id based on the bot type
    if bot_type == BotTypeChoice.user_bot:
        base_id = "knowledge"
    elif bot_type == BotTypeChoice.deep_dive:
        # For 'deep_dive', generate a random 5-digit number from range 1-9
        random_digits = "".join(map(str, random.sample(range(1, 9), 5)))
        base_id = f"engagement-survey-{random_digits}"
    elif bot_type == BotTypeChoice.subject_specific_bot:
        base_id = "subject-spe"
    else:
        base_id = bot_type

    # Create bot_id by combining the base_id, participant_id, and normalized bot_name
    bot_id = f"{base_id}-{participant_id[:5]}-{normalized_bot_name}"
    bot_id = bot_id.replace("_","-")

    return bot_id


def validate_access_code(tenant_id,client_name,user_id,access_code):
    client = ClientUserInfo.objects.filter(deleted=False, tenant_id=tenant_id,client_name=client_name).first()
    if not client:
        return {'error': 'Client not found'}, False

    user = User.objects.filter(deleted=False, uid=user_id).first()
    if not user:
        return {'error': 'User not found or already deleted'}, False

    access_code_obj = client.snippet_access_code.filter(deleted=False,is_active=True,access_code=access_code).first()
    if not access_code_obj:
        return {'error': 'Invalid access code'}, False
    if access_code_obj.is_temporary:
        logs = access_code_obj.logs.filter(deleted=False,user=user).first()
        if logs and logs.session_attempted >= access_code_obj.max_test_attempts:
            return {'error': 'access_code expired'}, False
        
    if not access_code_obj.is_active:
        return {'error': 'access_code expired'}, False
        
    
    AccessCodeLog.objects.get_or_create(
        access_code=access_code_obj,
        user=user
    )

    return {'success': 'Access code is valid'}, True
