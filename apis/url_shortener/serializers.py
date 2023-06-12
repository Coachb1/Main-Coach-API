from rest_framework import serializers
from url_shortener.models import UrlShortenerMap


class UrlShortenerSerializer(serializers.ModelSerializer):

    long_url_hash = serializers.CharField()
    short_url = serializers.CharField()
    long_url = serializers.CharField()

    class Meta:
        model = UrlShortenerMap
        fields = ("long_url_hash", "short_url", "long_url")


class UrlShortenerCheckSerializer(serializers.ModelSerializer):

    long_url_hash = serializers.CharField()

    class Meta:
        model = UrlShortenerMap
        fields = ("long_url_hash", )
