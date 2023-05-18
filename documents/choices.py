from djchoices import DjangoChoices, ChoiceItem


class DocTypeChoice(DjangoChoices):
    AUDIO_ANSWER = ChoiceItem("AUDIO_ANSWER")
    VIDEO_ANSWER = ChoiceItem("VIDEO_ANSWER")
    FLASH_CARD = ChoiceItem("FLASH_CARD")
    MIND_MAP = ChoiceItem("MIND_MAP")
    REPORT = ChoiceItem("REPORT")


class DocOwnerTypeChoice(DjangoChoices):
    user = ChoiceItem("user")
    system = ChoiceItem("system")
