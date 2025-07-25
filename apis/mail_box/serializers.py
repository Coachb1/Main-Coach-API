from rest_framework import serializers
from mail_box.models import MailBox, AuthorizedEmails, EmailConversation, AccountabilityIntake
from datetime import datetime, timezone, timedelta
import logging

logger = logging.getLogger('main')

class MailBoxViewSerializer(serializers.ModelSerializer):
    class Meta:
        model = MailBox
        fields = ['uid', 'email', 'prompt','grant_id' ,'followup_prompt','document_data','followup_prompt2',
                   'reward_prompt1', 'reward_prompt2',
                   'welcome_email_template', 'intake_reminder_email_template',
                    'intake_required', 'bot_name',
                    'intake_url','created', 'updated','knowledge_base']
        
        read_only_fields = ['uid', 'created', 'updated']

    def create(self, validated_data):
        mailbox = MailBox.objects.create(**validated_data)
        return mailbox
    
    def to_representation(self, instance):

        data = super().to_representation(instance)
        email_conversations = EmailConversation.objects.filter(mailbox_id=instance.uid)
        sender_last_bot_response = {}
        now_aware = datetime.now(timezone.utc)
        one_week_ago = now_aware - timedelta(days=7)

        for conv in email_conversations:
            sender = conv.sender
            if conv.responder == 'bot':
                # Record the bot's last response time
                sender_last_bot_response[sender] = {
                    'last_bot_response': conv.sent_at,
                    'user_responded': False,  # Initially set as False until a user response is found
                    'authorized_email': AuthorizedEmailsSerializer(
                        AuthorizedEmails.objects.filter(deleted=False, mailbox_id=conv.mailbox_id, email=conv.sender).last(), 
                    ).data
                }
            elif conv.responder == 'user':
                # If a user response is found after a bot response, update the user_responded flag
                if sender in sender_last_bot_response:
                    sender_last_bot_response[sender]['user_responded'] = True

        # Now calculate time since the bot's last response if the user hasn't responded back
        data['all_recipients'] = []
        for sender, info in sender_last_bot_response.items():
            weekly_interactions = EmailConversation.objects.filter(
                    mailbox_id=instance.uid,
                    sender=sender,
                    sent_at__range=[one_week_ago, now_aware],
                    responder='user'
                ).count()
            
            if not info['user_responded']:
                try:
                    last_bot_response_aware = info['last_bot_response'].astimezone(timezone.utc)

                    days_since_last_bot_response = (now_aware - last_bot_response_aware).days

                except Exception as e:
                    logger.exception(f'failed to calc last bot response time: {e}')
                    days_since_last_bot_response = (datetime.now() - info['last_bot_response']).days
                
                
                data['all_recipients'].append({
                    **info,
                    'last_responded': f"{days_since_last_bot_response} days since bot response, no user response",
                    'last_responded_in_days' : days_since_last_bot_response,
                    'weekly_interaction': weekly_interactions
                })
            else:
                data['all_recipients'].append({
                    **info,
                    'last_responded': "User has responded after the bot's response",
                    'last_responded_in_days': 0,
                    "weekly_interaction": weekly_interactions
                })

        return data

class AuthorizedEmailsSerializer(serializers.ModelSerializer):
    class Meta:
        model = AuthorizedEmails
        fields = ['uid', 'mailbox_id' ,'email', 'user_id', 'is_black_list',
                  'is_whitelist', 'name','age','goal','situation','followup_fequency',
                  'followup_escalation_email','reward_emails','is_intake_filled', 'created', 'updated']
        read_only_fields = ['uid','created','updated','uid']

    def create(self, validated_data):
        auth_email_user = AuthorizedEmails.objects.create(**validated_data)
        return auth_email_user
    
    def to_representation(self, instance):
        data = super().to_representation(instance)
        intake = AccountabilityIntake.objects.filter(email_address=instance.email).last()
        if intake:
            data['intake'] = AccountabilityIntakeSerializer(intake).data
        else:
            data['intake'] = {}

        return data

class EmailConversationSerializer(serializers.ModelSerializer):
    class Meta:
        model = EmailConversation
        fields = ['uid', 'mailbox_id', 'sender', 'subject', 
                  'body', 'sent_at','responder','created', 'updated']
        read_only_fields = ['uid', 'created', 'updated']
    def create(self, validated_data):
        email_conversation = EmailConversation.objects.create(**validated_data)
        return email_conversation
    
    
class AccountabilityIntakeSerializer(serializers.ModelSerializer):
    class Meta:
        model = AccountabilityIntake
        fields = '__all__'
        read_only_fields = ['uid']
    def create(self, validated_data):
        accountability_intake = AccountabilityIntake.objects.create(**validated_data)
        return accountability_intake