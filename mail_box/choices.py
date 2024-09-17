from djchoices import ChoiceItem, DjangoChoices


class FollowupFreqType(DjangoChoices):
    weekly = ChoiceItem("weekly")
    daily = ChoiceItem("daily")
    monthly = ChoiceItem('monthly')
    nan = ChoiceItem('nan')
    never = ChoiceItem('never')
    alternate = ChoiceItem('alternate')


    