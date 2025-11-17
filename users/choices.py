from djchoices import DjangoChoices, ChoiceItem


class UserRoleChoice(DjangoChoices):
    admin = ChoiceItem("admin")
    member = ChoiceItem("member")
    client_admin = ChoiceItem("client_admin")
    super_admin = ChoiceItem("super_admin")
    deep_dive_creator = ChoiceItem("deep_dive_creator")

class StatusChoice(DjangoChoices):
    available = ChoiceItem("available")
    booked = ChoiceItem("booked")

class LLMChoice(DjangoChoices):
    gpt = ChoiceItem("gpt")
    anthropic = ChoiceItem("anthropic")
    gemini = ChoiceItem("gemini")
    caching_anthropic = ChoiceItem("caching_anthropic")


class ProfileTypeChoice(DjangoChoices):
    coach = ChoiceItem("coach")
    coachee = ChoiceItem("coachee")
    mentor = ChoiceItem("mentor")
    mentee = ChoiceItem("mentee")
    coach_mentor = ChoiceItem("coach-mentor") # it has "-" because it contains two profiletype
    skill_bot = ChoiceItem("skill_bot")
    coachbots = ChoiceItem("coachbots")
    external = ChoiceItem('external')
    icons_by_ai = ChoiceItem('icons_by_ai')
    knowledge_bot = ChoiceItem('knowledge_bot')
    customer_avatar = ChoiceItem('customer_avatar')
    deep_dive = ChoiceItem("deep_dive")


class BotTypeChoice(DjangoChoices):
    avatar_bot = ChoiceItem("avatar_bot")
    subject_specific_bot = ChoiceItem("subject_specific_bot")
    feedback_bot = ChoiceItem("feedback_bot")
    subject_matter_bot = ChoiceItem("subject_matter_bot")
    helper_bot = ChoiceItem("helper_bot")
    coachbots = ChoiceItem("coachbots")
    user_bot = ChoiceItem("user_bot")
    deep_dive = ChoiceItem("deep_dive")



class CoachCoacheeConnectionStatusChoice(DjangoChoices):
    pending = ChoiceItem("pending")
    accepted = ChoiceItem("accepted")
    rejected = ChoiceItem("rejected")
    blocked = ChoiceItem("blocked")
    removed = ChoiceItem("removed")




def get_default_library_bot_button_controls():
    return {
        "leaderboard_button": {"label": "LeaderBoard", "show": True},
        "idea_board_button": {"label": "IdeaBoard", "show": True},
        "ai_pulse": {"label": "AI Pulse Report", "show": True}
    }