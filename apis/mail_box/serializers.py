from rest_framework import serializers
from mail_box.models import MailBox, AuthorizedEmails, EmailConversation
from datetime import datetime, timezone
import logging

logger = logging.getLogger('main')

class MailBoxViewSerializer(serializers.ModelSerializer):
    class Meta:
        model = MailBox
        fields = ['uid', 'email', 'prompt', 'followup_prompt','document_data','created', 'updated']
        read_only_fields = ['uid', 'created', 'updated']

    def create(self, validated_data):
        mailbox = MailBox.objects.create(**validated_data)
        return mailbox
    
    def to_representation(self, instance):

        data = super().to_representation(instance)
        email_conversations = EmailConversation.objects.filter(mailbox_id=instance.uid)
        sender_last_bot_response = {}
        # list_of_sender = set(list(email_conversations.values_list('sender','responder')))
        # print(list_of_sender)
        for conv in email_conversations:
            sender = conv.sender
            if conv.responder == 'bot':
                # Record the bot's last response time
                sender_last_bot_response[sender] = {
                    'last_bot_response': conv.sent_at,
                    'user_responded': False  # Initially set as False until a user response is found
                }
            elif conv.responder == 'user':
                # If a user response is found after a bot response, update the user_responded flag
                if sender in sender_last_bot_response:
                    sender_last_bot_response[sender]['user_responded'] = True

        # Now calculate time since the bot's last response if the user hasn't responded back
        data['all_recipients'] = []
        for sender, info in sender_last_bot_response.items():
            if not info['user_responded']:
                try:
                    now_aware = datetime.now(timezone.utc)
                    last_bot_response_aware = info['last_bot_response'].astimezone(timezone.utc)

                    days_since_last_bot_response = (now_aware - last_bot_response_aware).days

                except Exception as e:
                    logger.exception(f'failed to calc last bot response time: {e}')
                    days_since_last_bot_response = (datetime.now() - info['last_bot_response']).days
                    
                data['all_recipients'].append({
                    'email': sender,
                    'last_responded': f"{days_since_last_bot_response} days since bot response, no user response",
                    'last_responded_in_number' : days_since_last_bot_response
                })
            else:
                data['all_recipients'].append({
                    'email': sender,
                    'last_responded': "User has responded after the bot's response",
                    'last_responded_in_number': 0
                })

        return data

class AuthorizedEmailsSerializer(serializers.ModelSerializer):
    class Meta:
        model = AuthorizedEmails
        fields = ['uid', 'email', 'user_id', 'is_black_list','is_whitelist', 'created', 'updated']

class EmailConversationSerializer(serializers.ModelSerializer):
    class Meta:
        model = EmailConversation
        fields = ['uid', 'mailbox_id', 'sender', 'subject', 'body', 'sent_at', 'responder', 'created', 'updated']
        read_only_fields = ['uid', 'created', 'updated']
    def create(self, validated_data):
        email_conversation = EmailConversation.objects.create(**validated_data)
        return email_conversation