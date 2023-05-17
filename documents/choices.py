from djchoices import DjangoChoices, ChoiceItem


class DocTypeChoice(DjangoChoices):
    AUDIO_ANSWER = ChoiceItem("AUDIO_ANSWER")
    VIDEO_ANSWER = ChoiceItem("VIDEO_ANSWER")
    FLASH_CARD = ChoiceItem("FLASH_CARD")


class DocOwnerTypeChoice(DjangoChoices):
    user = ChoiceItem("user")
    system = ChoiceItem("system")
