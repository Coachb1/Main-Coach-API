from django import forms
from django.core.exceptions import ValidationError
from tests.helpers import parse_psychometric_csv
from django.db import transaction
from tenants.models import Tenant
from tests.models import Psychometric, PsychometricItem
from django.utils.translation import gettext_lazy as _
import csv
from .models import PsychometricReportSection, PsychometricReportSubsection, Test
from io import TextIOWrapper


class CSVUploadForm(forms.Form):
    csv_file = forms.FileField(max_length=1, required=True)

    def __init__(self, *args, **kwargs):
        show_tenant_id = kwargs.pop('show_tenant_id', True)
        super().__init__(*args, **kwargs)
        
        if show_tenant_id:
            self.fields['tenant_id'] = forms.ChoiceField(
                choices=[(None, _("Select a tenant - (None)"))] + Tenant.get_tenant_choices(),
                required=True,
            )

    def clean_csv_file(self):
        file = self.cleaned_data.get("csv_file")

        # ✅ Restrict file type to CSV
        if not file.name.endswith('.csv'):
            raise forms.ValidationError("Invalid file type. Please upload a CSV file.")

        # ✅ Ensure only one file is uploaded
        if file.multiple_chunks():  # In case of large files, this prevents multiple file uploads
            raise forms.ValidationError("You can only upload one file at a time.")
        
        if file.size == 0:
            raise forms.ValidationError("Uploaded file is empty. Please select a valid CSV file.")


        return file

class PsychometricAdminForm(forms.ModelForm):
    csv_file = forms.FileField(
        required=False,
        help_text=_("Upload a CSV file to create Psychometric Items automatically.")
    )
    tenant_id = forms.ChoiceField(
        choices=[(None, _("Select a tenant - (None)"))] + Tenant.get_tenant_choices(),  # Fetch all tenants from the database
        required=False,  # Set this to True or False depending on your requirements
        help_text=_("Select the tenant associated with this Psychometric item."),
        initial=None
    )


    class Meta:
        model = Psychometric
        fields = ('name', 'description', 'deleted')

    def clean(self):
        cleaned_data = super().clean()
        csv_file = cleaned_data.get('csv_file')
        tenant_id = cleaned_data.get('tenant_id')

        # Handle saving None if tenant_id is not selected
        if tenant_id == '':
            cleaned_data['tenant_id'] = None 

        if not self.instance.pk:  # Check if this is a new instance (not saved yet)
            if not csv_file:
                raise ValidationError(_("A CSV file is required during creation."))
            # Ensure it's a CSV file by checking the file type
            if not csv_file.name.endswith('.csv'):
                raise ValidationError(_("File must be a CSV."))
            
        if csv_file:
            try:
                # Parse CSV to extract PsychometricItem data
                items_data = parse_psychometric_csv(csv_file=csv_file)

                # Create the Psychometric instance temporarily to get its pk
                with transaction.atomic():
                    # Save the Psychometric instance temporarily to fetch its pk
                    psychometric_instance = self.instance
                    psychometric_instance.save()

                    # Prepare a list of PsychometricItem instances to be created
                    psychometric_items = []
                    for item_data in items_data:
                        # Assuming item_data is a dictionary with field names matching the model
                        psychometric_item = PsychometricItem(
                            **item_data,
                            psychometric=psychometric_instance  # Associate these items with the current Psychometric instance
                        )
                        psychometric_items.append(psychometric_item)

                    # Use bulk_create for efficient database insertions
                    PsychometricItem.objects.bulk_create(psychometric_items)

                    # Optionally, store items_data if you want to reference them later
                    cleaned_data['items_data'] = items_data

                    # After bulk_create, manually handle saving the Psychometric instance if needed
                    # If necessary, save the Psychometric instance after items are created

            except ValidationError as e:
                raise ValidationError(_(f"Error parsing CSV file: {e}"))
            
        return cleaned_data    
          

class PsychometricReportAdminForm(forms.ModelForm):
    csv_file = forms.FileField(
        required=False,
        help_text=_("Upload a CSV file to create/update Psychometric report config")
    )


    class Meta:
        model = PsychometricReportSection
        fields = '__all__'

    def clean(self):
        cleaned_data = super().clean()
        csv_file = cleaned_data.get('csv_file')

            
        if csv_file and not csv_file.name.endswith('.csv'):
            raise ValidationError(_("File must be a CSV."))
        
        if csv_file:
            try:
                with transaction.atomic():
                    section = self.instance
                    section.save()

                    self.process_csv(csv_file=csv_file,section=section)
            except ValidationError as e:
                raise ValidationError(_(f"Error parsing CSV file: {e}"))
            
        return cleaned_data  


    def process_csv(self, csv_file, section:PsychometricReportSection):
        try:
            # Decode and read the CSV file
            decoded_file = TextIOWrapper(csv_file, encoding='utf-8')
            reader = csv.DictReader(decoded_file)
            name = section.name

            # Process the CSV rows and create subsections
            for row in reader:
                section_name = row.get('section_name')
                section_value = row.get('section_value')
                section_footer = row.get('section_footer')
                subsection_name = row.get('subsection_name')
                subsection_value = row.get('subsection_value')
                subsection_footer = row.get('subsection_footer')
                subsection_parent_name = row.get('subsection_parent_name')
                range_value = row.get('range')

                # If the section_name in the CSV matches the main section, update its value and footer
                if section_name == name:
                    if section_value or section_footer:
                        section.value = section_value
                        section.footer = section_footer
                        section.save()

                #creating section as a subsection to original section[name]
                if not subsection_name:
                    PsychometricReportSubsection.objects.update_or_create(
                        name=section_name,
                        section=section,
                        defaults={
                            'value': section_value,
                            'footer': section_footer
                        }
                    )

                # Create or update Subsection under the corresponding Section
                if subsection_name:
                    parent = None
                    if subsection_parent_name:
                        parent = PsychometricReportSubsection.objects.filter(name=subsection_parent_name,section=section).first()

                    # Update or create the Subsection under the correct Section
                    PsychometricReportSubsection.objects.update_or_create(
                        name=subsection_name,
                        section=section,
                        defaults={
                            'value': subsection_value,
                            'parent': parent,
                            'range_value': range_value,
                            'footer': subsection_footer
                        }
                    )

        except Exception as e:
            raise ValidationError(f"Error processing CSV: {str(e)}") 



class BulkUpdateForm(forms.Form):
    _selected_action = forms.CharField(widget=forms.MultipleHiddenInput)
    tab_category = forms.CharField(required=False)
    tab_type = forms.CharField(required=False)
    tab_difficulty = forms.CharField(required=False)
    tab_sticker = forms.CharField(required=False)