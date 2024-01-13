from djchoices import DjangoChoices, ChoiceItem


class UserRoleChoice(DjangoChoices):
    admin = ChoiceItem("admin")
    member = ChoiceItem("member")
    client_admin = ChoiceItem("client_admin")


class ProfileTypeChoice(DjangoChoices):
    coach = ChoiceItem("coach")
    coachee = ChoiceItem("coachee")
    mentor = ChoiceItem("mentor")
    mentee = ChoiceItem("mentee")