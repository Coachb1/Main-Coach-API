from djchoices import DjangoChoices, ChoiceItem


class DocTypeChoice(DjangoChoices):
    AUDIO_ANSWER = ChoiceItem("AUDIO_ANSWER")
    VIDEO_ANSWER = ChoiceItem("VIDEO_ANSWER")


class DocOwnerTypeChoice(DjangoChoices):
    user = ChoiceItem("user")
    system = ChoiceItem("system")
