from django.contrib import admin
from sso.models import UserIdentityProvider


@admin.register(UserIdentityProvider)
class UserIdentityProviderAdmin(admin.ModelAdmin):
    list_display = ('uid', 'user', 'provider', 'email', 'last_login', 'first_login')
    list_filter = ('provider', 'created', 'last_login')
    search_fields = ('email', 'provider_id', 'user__uid')
    readonly_fields = ('uid', 'created', 'updated', 'first_login')
    
    fieldsets = (
        ('Identity', {
            'fields': ('user', 'provider', 'provider_id', 'tid')
        }),
        ('User Info', {
            'fields': ('email',)
        }),
        ('Claims Data', {
            'fields': ('raw_claims',),
            'classes': ('collapse',)
        }),
        ('Timestamps', {
            'fields': ('first_login', 'last_login', 'created', 'updated'),
            'classes': ('collapse',)
        }),
        ('System', {
            'fields': ('uid', 'deleted'),
            'classes': ('collapse',)
        }),
    )
    
    def has_add_permission(self, request):
        # Identity providers should be created via SSO flow, not manually
        return False
    
    def has_delete_permission(self, request, obj=None):
        # Prevent accidental deletion, but can be changed if needed
        return request.user.is_superuser
