from users.helpers import get_user_attribute
from users.models import User
import re


def get_user_by_id(user_id) -> User:
    return User.objects.get(deleted=False,uid=user_id)


def get_user_display_name(user: User):
    name = ""
    slack_profile_attribute = get_user_attribute(user, tag="slack_profile")
    if slack_profile_attribute:
        name = f"{slack_profile_attribute.attributes.get('real_name')} (username: {slack_profile_attribute.attributes.get('name')})"

    else:
        whatsapp_profile_attribute = get_user_attribute(
            user, tag="whatsapp_profile")
        if whatsapp_profile_attribute:
            name = whatsapp_profile_attribute.attributes.get("user_name")
            mobile_number = whatsapp_profile_attribute.attributes.get(
                "mobile_number")

            name = f"{name} ({mobile_number})"

    if not name:
        name = user.name
        name = re.sub(r'[_-]+', ' ', name)

    return name
