
from django import forms

from users.models import ClientResource



class BulkResourceActionForm(forms.Form):
    """Form used in the bulk resource assign/deassign intermediate page."""
    action_type = forms.ChoiceField(
        choices=[("assign", "Assign"), ("deassign", "Deassign")],
        widget=forms.RadioSelect,
        initial="assign",
    )
    resources = forms.ModelMultipleChoiceField(
        queryset=ClientResource.objects.all(),  # adjust to your actual Resource model/queryset
        widget=forms.CheckboxSelectMultiple,
        required=True,
        label="Resources",
    )

