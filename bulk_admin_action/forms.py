from django import forms

class UploadFileForm(forms.Form):
    llm_type = forms.ChoiceField(choices=[('gemini', 'Gemini'),('anthropic', 'Anthropic')])
    email = forms.EmailField(label='Your Email')
    domain = forms.CharField(label='Domain')
    password = forms.CharField(widget=forms.PasswordInput(), label='Password')
    file = forms.FileField(
        label="Upload CSV",
        widget=forms.ClearableFileInput(attrs={
            'autocomplete':'off'
        })
    )
class UploadCsvForm(forms.Form):
    email = forms.EmailField(label='Email')
    domain = forms.CharField(label='Domain')
    password = forms.CharField(widget=forms.PasswordInput(), label='Password')
    test_type=forms.ChoiceField(choices=[('static', 'Static'), ('dynamic', 'Dynamic')])
    file = forms.FileField(
        label="Upload CSV",
        widget=forms.ClearableFileInput(attrs={
            'autocomplete':'off'
        })
    )
class TestForm(forms.Form):
    # llm_type = forms.ChoiceField(choices=[('gemini', 'Gemini'),('anthropic', 'Anthropic')])
    email = forms.EmailField(label='Email')
    domain = forms.CharField(label='Domain')
    password = forms.CharField(widget=forms.PasswordInput(), label='Password')
    test_code = forms.CharField(label='TestCode')
class CreateScenarioForm(forms.Form):
    llm_type = forms.ChoiceField(choices=[('gemini', 'Gemini'),('anthropic', 'Anthropic')])
    file = forms.FileField(
        label="Upload CSV",
        widget=forms.ClearableFileInput(attrs={
            'autocomplete':'off'
        })
    )

class BulkGeminiPromptProcessor(forms.Form):
    llm_type = forms.ChoiceField(choices=[('gemini', 'Gemini'),('anthropic', 'Anthropic')])
    csv_file = forms.FileField(label="Upload CSV")
    


class NormalCSVForm(forms.Form):
    DROPDOWN_CHOICES = [
        ('test_code', 'Via Test Code'),
        ('others', 'Others'),
    ]
    
    dropdown = forms.ChoiceField(choices=DROPDOWN_CHOICES, label="Create Method")

    # Always Required
    email = forms.EmailField(required=True)
    password = forms.CharField(widget=forms.PasswordInput, required=True)
    subdomain_prefix = forms.CharField(required=True)
    
    title = forms.CharField(required=False)
    test_type = forms.CharField(required=True, initial='test')
    interaction_mode = forms.CharField(required=False)
    scenario_case = forms.CharField(required=False)
    num_questions = forms.IntegerField(required=True, min_value=1, initial=6)
    candidate_type = forms.CharField(required=False)
    creator_email = forms.EmailField(required=False)
    
    # Optional fields you mentioned in original code
    test_codes = forms.CharField(required=False)
    page_name = forms.CharField(required=False)
    competency_skills = forms.BooleanField(required=False, initial=True)
    tab_category = forms.CharField(required=False)
    client_name = forms.CharField(required=False)


class DynamicCsvForm(forms.Form):
    DROPDOWN_CHOICES = [
        ('test_code', 'Via Test Code'),
        ('others', 'Others'),
    ]
    
    dropdown = forms.ChoiceField(choices=DROPDOWN_CHOICES, label="Create Method")

    # Always Required
    email = forms.EmailField(required=True)
    password = forms.CharField(widget=forms.PasswordInput, required=True)
    subdomain_prefix = forms.CharField(required=True)
    
    
    bots = forms.IntegerField(min_value=1, label="Number of Bots", initial=1)
    is_start_with_user = forms.ChoiceField(choices=[('true', 'True'), ('false', 'False')], label="Starts with User", initial='false')
    title = forms.CharField(required=False)
    test_type = forms.ChoiceField(required=True, choices=[('dynamic_discussion_thread', 'Dynamic Discussion Thread'), ('test', 'Test')], initial='dynamic_discussion_thread')
    interaction_mode = forms.ChoiceField(required=False, choices=[('single', 'Single'), ('multiple', 'Multiple')])
    scenario_case = forms.CharField(required=False)
    num_questions = forms.IntegerField(required=True, min_value=1, initial=6)
    candidate_type = forms.CharField(required=False)
    creator_email = forms.EmailField(required=False)
    
    # Optional fields you mentioned in original code
    test_codes = forms.CharField(required=False)
    page_name = forms.CharField(required=False)
    competency_skills = forms.BooleanField(required=False, initial=True)
    tab_category = forms.CharField(required=False)
    client_name = forms.CharField(required=False)