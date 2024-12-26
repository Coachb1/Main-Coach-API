from django.contrib import admin
from import_export.admin import ExportActionMixin
from tenants.models import Tenant

from django import forms



class TenantAdmin(ExportActionMixin, admin.ModelAdmin):
    list_per_page = 10
    list_display = ('id','uid','name','subdomain_prefix','logo','test_per_month','mobile_number_restriction_whatsapp','mobile_number_list','use_skills_from_skill_bank')
    search_fields = ('subdomain_prefix','name')
    list_editable = ('logo','test_per_month','mobile_number_restriction_whatsapp','mobile_number_list','use_skills_from_skill_bank')

admin.site.register(Tenant, TenantAdmin)



# Custom form to handle tenant_id dropdown
class TenantAwareAdminForm(forms.ModelForm):
    tenant_id = forms.ChoiceField(choices= [(None, 'Select Tenant')]+ Tenant.get_tenant_choices())

    class Meta:
        model = None  # We'll set the model dynamically in the admin
        fields = '__all__'

class TenantFilter(admin.SimpleListFilter):
    title: str = 'tenant'
    parameter_name = 'tenant'

    def lookups(self, request, model_admin):
        # This returns a list of tuples with tenant choices
        return Tenant.get_tenant_choices()

    def queryset(self, request, queryset):
    # Print the filtering value
        print(f"Filtering by tenant_id: {self.value()}")
        
        # Print the model name
        model_name = queryset.model.__name__  # Get the model name
        print(f"Filtering on model: {model_name}")

        if self.value():
            return queryset.filter(tenant_id=self.value())
        
        return queryset
    

# Base admin class for Tenant-aware models
class TenantAwareModelAdmin(admin.ModelAdmin):
    def __init__(self, model, admin_site):
        super().__init__(model, admin_site)
        # Append tenant_id to list_filter only if it doesn't exist already
        self.list_filter = (TenantFilter,) + getattr(self, 'list_filter', ())
    

    def get_form(self, request, obj=None, **kwargs):
        # Check if the model has the 'tenant_id' field
        if 'tenant_id' in [f.name for f in self.model._meta.fields]:
            # Dynamically create the form class with the correct Meta model
            class DynamicTenantAwareForm(TenantAwareAdminForm):
                class Meta(TenantAwareAdminForm.Meta):
                    model = self.model

            # Return the dynamically created form
            kwargs['form'] = DynamicTenantAwareForm
            kwargs['list_filter'] = (TenantFilter,) + getattr(self, 'list_filter', ())
            if 'tenant_id' not in getattr(self, 'list_display', ()):
                kwargs['list_display'] = getattr(self, 'list_display', ()) + ('tenant_id',)

        print(f"kwargs: {kwargs}")
        
        return super().get_form(request, obj, **kwargs)