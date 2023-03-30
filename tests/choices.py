from djchoices import DjangoChoices, ChoiceItem


class InteractionModeChoices(DjangoChoices):
    text = ChoiceItem("text")
    audio = ChoiceItem("audio")
    video = ChoiceItem("video")


class TestAttemptSessionStatusChoices(DjangoChoices):
    in_progress = ChoiceItem("in_progress")
    completed = ChoiceItem("completed")
    cancelled = ChoiceItem("cancelled")


class QuestionTypeChoices(DjangoChoices):
    subjective = ChoiceItem("subjective")
    objective = ChoiceItem("objective")
    mcq = ChoiceItem("mcq")


class QuestionResponseTypeChoices(DjangoChoices):
    text = ChoiceItem("text")
    audio = ChoiceItem("audio")
    video = ChoiceItem("video")


class TestQuestionResponseEvaluationStatusChoices(DjangoChoices):
    init = ChoiceItem("init")
    in_progress = ChoiceItem("in_progress")
    success = ChoiceItem("success")
    failed = ChoiceItem("failed")
