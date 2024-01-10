from django.contrib import admin

from .models import BotAttribute, SignatureBot, ClientUserInfo
admin.site.register(BotAttribute)
admin.site.register(SignatureBot)
admin.site.register(ClientUserInfo)