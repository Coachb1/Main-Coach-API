from djchoices import ChoiceItem, DjangoChoices


class RoleType(DjangoChoices):
    assistant = ChoiceItem("assistant")
    user = ChoiceItem("user")

class RoleAndPermissionType(DjangoChoices):
    premimum = ChoiceItem('premimum')
    demo = ChoiceItem('demo')

    