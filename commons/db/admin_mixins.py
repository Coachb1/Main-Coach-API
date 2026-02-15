# admin_mixins.py (create this new file in your app)

from django.contrib import admin
from django.utils.html import format_html
from django.db.models import Q
from django.urls import path
from django.template.response import TemplateResponse
from django.core.paginator import Paginator

class SearchablePaginatedInlineMixin:
    """
    Reusable mixin for making any inline searchable and paginated.
    
    Usage:
        class MyInline(SearchablePaginatedInlineMixin, admin.TabularInline):
            model = MyModel
            search_fields = ['field1', 'field2']  # Fields to search
            items_per_page = 10  # Default items to show
    """
    
    # Configuration options - override these in your inline class
    search_fields = []  # List of fields to search
    items_per_page = 5  # Initial number of items to show
    extra = 0  # Don't show extra empty rows
    can_delete = True
    show_change_link = True
    classes = ['collapse']
    
    # Use custom template
    template = 'admin/inlines/searchable_paginated_inline.html'
    
    def get_formset(self, request, obj=None, **kwargs):
        """Add search context to formset"""
        formset = super().get_formset(request, obj, **kwargs)
        
        # Add configuration to formset for template
        formset.search_fields = self.search_fields
        formset.items_per_page = self.items_per_page
        formset.inline_title = self.verbose_name_plural if hasattr(self, 'verbose_name_plural') else self.model._meta.verbose_name_plural
        
        return formset


class AdvancedInlineAdminMixin:
    """
    Mixin for admin classes that have advanced inlines.
    Provides a dedicated view for managing inline items with full pagination.
    
    Usage:
        class MyAdmin(AdvancedInlineAdminMixin, admin.ModelAdmin):
            model = MyModel
            inlines = [MyInline]
    """
    
    def get_urls(self):
        """Add custom URLs for inline management"""
        urls = super().get_urls()
        custom_urls = []
        
        for inline_class in self.inlines:
            if hasattr(inline_class, 'model'):
                model_name = inline_class.model._meta.model_name
                custom_urls.append(
                    path(
                        f'<path:object_id>/{model_name}/',
                        self.admin_site.admin_view(self.inline_items_view),
                        name=f'{self.model._meta.app_label}_{self.model._meta.model_name}_{model_name}',
                        kwargs={'inline_class': inline_class}
                    ),
                )
        
        return custom_urls + urls
    
    def inline_items_view(self, request, object_id, inline_class):
        """Generic view for managing any inline items with pagination"""
        obj = self.get_object(request, object_id)
        
        if obj is None:
            return self._get_obj_does_not_exist_redirect(request, self.model._meta, object_id)
        
        # Get the related manager
        relation_name = self._get_relation_name(inline_class)
        if not relation_name:
            raise ValueError(f"Could not find relation for {inline_class.model}")
        
        related_manager = getattr(obj, relation_name)
        
        # Get pagination parameters
        page = int(request.GET.get('page', 1))
        per_page = int(request.GET.get('per_page', 20))
        search = request.GET.get('search', '')
        
        # Filter items
        items = related_manager.all()
        
        if search and hasattr(inline_class, 'search_fields'):
            q_objects = Q()
            for field in inline_class.search_fields:
                q_objects |= Q(**{f'{field}__icontains': search})
            items = items.filter(q_objects)
        
        # Paginate
        paginator = Paginator(items, per_page)
        page_obj = paginator.get_page(page)
        
        context = {
            'parent_obj': obj,
            'parent_model': self.model,
            'inline_model': inline_class.model,
            'inline_title': inline_class.model._meta.verbose_name_plural,
            'page_obj': page_obj,
            'search': search,
            'fields': inline_class.fields if hasattr(inline_class, 'fields') else None,
            'opts': self.model._meta,
            'has_view_permission': self.has_view_permission(request),
            'has_add_permission': self.has_add_permission(request),
            'has_change_permission': self.has_change_permission(request),
            'has_delete_permission': self.has_delete_permission(request),
        }
        
        return TemplateResponse(
            request,
            'admin/inlines/inline_items_view.html',
            context
        )
    
    def _get_relation_name(self, inline_class):
        """Find the relation name between parent and inline model"""
        for field in self.model._meta.get_fields():
            if field.is_relation and field.related_model == inline_class.model:
                return field.get_accessor_name()
        return None
    
    def get_inline_count(self, obj, inline_class):
        """Helper method to get count of inline items"""
        relation_name = self._get_relation_name(inline_class)
        if relation_name:
            return getattr(obj, relation_name).count()
        return 0