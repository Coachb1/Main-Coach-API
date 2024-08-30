from rest_framework import serializers
from mail_box.models import MailBox, AuthorizedEmails, EmailConversation

class MailBoxViewSerializer(serializers.ModelSerializer):
    class Meta:
        model = MailBox
        fields = ['uid', 'email', 'prompt', 'created', 'updated']
        read_only_fields = ['uid', 'created', 'updated']

    def create(self, validated_data):
        mailbox = MailBox.objects.create(**validated_data)
        return mailbox

class AuthorizedEmailsSerializer(serializers.ModelSerializer):
    class Meta:
        model = AuthorizedEmails
        fields = ['uid', 'email', 'user_id', 'is_black_list', 'created', 'updated']

class EmailConversationSerializer(serializers.ModelSerializer):
    class Meta:
        model = EmailConversation
        fields = ['uid', 'mailbox_id', 'sender', 'subject', 'body', 'sent_at', 'responder', 'created', 'updated']
        read_only_fields = ['uid', 'created', 'updated']
    def create(self, validated_data):
        email_conversation = EmailConversation.objects.create(**validated_data)
        return email_conversation