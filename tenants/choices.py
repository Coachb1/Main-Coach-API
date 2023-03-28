from djchoices import DjangoChoices, ChoiceItem


class SubscriptionChoices(DjangoChoices):
    enabled = ChoiceItem("enabled")
    paused = ChoiceItem("paused")
    discontinued = ChoiceItem("discontinued")
