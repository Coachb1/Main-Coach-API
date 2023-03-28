from djchoices import DjangoChoices, ChoiceItem


class InteractionModeChoices(DjangoChoices):
    audio = ChoiceItem("audio")
    video = ChoiceItem("video")
