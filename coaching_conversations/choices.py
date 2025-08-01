from djchoices import DjangoChoices, ChoiceItem


class CoachingConversationChoices(DjangoChoices):
    bot_message_saved = ChoiceItem("bot_message_saved")
    participant_message_saved = ChoiceItem("participant_message_saved")
    conversation_finished = ChoiceItem("conversation_finished")

class BotScenarioCaseChoice(DjangoChoices):
    role_bot = ChoiceItem('role_bot')
    skill_bot = ChoiceItem('skill_bot')
    skill_guide = ChoiceItem('skill_guide')
    general = ChoiceItem('general')
    icons_by_ai = ChoiceItem('icons_by_ai')
    customer_avatar = ChoiceItem('customer_avatar')
    ai_agent = ChoiceItem('ai_agent') # In this type of bot no databsase user, bot anything you will not pass
