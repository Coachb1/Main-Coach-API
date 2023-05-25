from users.models import User


def get_user_by_id(user_id) -> User:
    return User.objects.get(uid=user_id)