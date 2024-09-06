from djchoices import ChoiceItem, DjangoChoices


class FollowupFreqType(DjangoChoices):
    weekly = ChoiceItem("weekly")
    daily = ChoiceItem("daily")
    monthly = ChoiceItem('monthly')
    nan = ChoiceItem('nan')


    