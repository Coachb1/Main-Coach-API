from djchoices import DjangoChoices, ChoiceItem


class UserRoleChoice(DjangoChoices):
    admin = ChoiceItem("admin")
    member = ChoiceItem("member")
    client_admin = ChoiceItem("client_admin")

class StatusChoice(DjangoChoices):
    available = ChoiceItem("available")
    booked = ChoiceItem("booked")


class ProfileTypeChoice(DjangoChoices):
    coach = ChoiceItem("coach")
    coachee = ChoiceItem("coachee")
    mentor = ChoiceItem("mentor")
    mentee = ChoiceItem("mentee")


class BotTypeChoice(DjangoChoices):
    avatar_bot = ChoiceItem("avatar_bot")
    feedback_bot = ChoiceItem("feedback_bot")
    subject_matter_bot = ChoiceItem("subject_matter_bot")
    helper_bot = ChoiceItem("helper_bot")