
from django import forms

from commons.db.json_form_mixins import UniversalSchemaWidget
from jobaid.models import JobAid
from jobaid.schema import LABELS_SCHEMA
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

class JobAidForm(forms.ModelForm):
    class Meta:
        model = JobAid
        fields = '__all__'
        widgets = {
            'labels': UniversalSchemaWidget(LABELS_SCHEMA)
        }