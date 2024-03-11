from djchoices import DjangoChoices, ChoiceItem


class UserRoleChoice(DjangoChoices):
    admin = ChoiceItem("admin")
    member = ChoiceItem("member")
    client_admin = ChoiceItem("client_admin")
    super_admin = ChoiceItem("super_admin")

class StatusChoice(DjangoChoices):
    available = ChoiceItem("available")
    booked = ChoiceItem("booked")


class ProfileTypeChoice(DjangoChoices):
    coach = ChoiceItem("coach")
    coachee = ChoiceItem("coachee")
    mentor = ChoiceItem("mentor")
    mentee = ChoiceItem("mentee")
    coach_mentor = ChoiceItem("coach-mentor") # it has "-" because it contains two profiletype
    skill_bot = ChoiceItem("skill_bot")
    coachbots = ChoiceItem("coachbots")
    external = ChoiceItem('external')


class BotTypeChoice(DjangoChoices):
    avatar_bot = ChoiceItem("avatar_bot")
    feedback_bot = ChoiceItem("feedback_bot")
    subject_matter_bot = ChoiceItem("subject_matter_bot")
    helper_bot = ChoiceItem("helper_bot")
    coachbots = ChoiceItem("coachbots")
    user_bot = ChoiceItem("user_bot")



class CoachCoacheeConnectionStatusChoice(DjangoChoices):
    pending = ChoiceItem("pending")
    accepted = ChoiceItem("accepted")
    rejected = ChoiceItem("rejected")
    blocked = ChoiceItem("blocked")
    removed = ChoiceItem("removed")