from users.helpers import get_user_attribute
from users.models import User


def get_user_by_id(user_id) -> User:
    return User.objects.get(uid=user_id)


def get_user_display_name(user: User):
    name = ""
    slack_profile_attribute = get_user_attribute(user, tag="slack_profile")
    if slack_profile_attribute:
        name = slack_profile_attribute.attributes.get("real_name")

    if not name:
        name = user.name

    return name
