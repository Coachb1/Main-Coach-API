from djchoices import ChoiceItem, DjangoChoices

class CultureMapSkillTypeChoices(DjangoChoices):
    ocean_model = ChoiceItem('ocean_model')
    communication_skills = ChoiceItem('communication_skills')
    workspace_skills = ChoiceItem('workspace_skills')

