from djchoices import DjangoChoices, ChoiceItem


class CoachingConversationChoices(DjangoChoices):
    bot_message_saved = ChoiceItem("bot_message_saved")
    participant_message_saved = ChoiceItem("participant_message_saved")
    conversation_finished = ChoiceItem("conversation_finished")
