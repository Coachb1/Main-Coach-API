from rest_framework import serializers

from identities.helpers import get_user_identities
from identities.serializers import IdentityUserViewSerializer
from users.models import User
