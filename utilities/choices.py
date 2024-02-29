from djchoices import DjangoChoices, ChoiceItem


class UserCanJoinAsChoices(DjangoChoices):
    coach = ChoiceItem("coach")
    mentor = ChoiceItem("mentor")
    coachee = ChoiceItem("coachee")
    mentee = ChoiceItem("mentee")