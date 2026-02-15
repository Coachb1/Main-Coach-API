import json
from django import forms
from django.template.loader import render_to_string
from django.utils.safestring import mark_safe

class UniversalSchemaWidget(forms.Textarea):
    template_name = 'admin/json_builder_change_form.html'

    def __init__(self, schema, attrs=None):
        self.schema = schema
        super().__init__(attrs)

    def format_value(self, value):
        """
        Robust formatting that handles:
        1. None -> Empty JSON object '{}'
        2. Dict/List (Database data) -> JSON String
        3. String (Form re-submission data) -> Return as-is (don't double encode)
        """
        if value is None:
            return '{}'
        
        # If it's already a string (happens during form errors/re-render),
        # try to clean it, but DO NOT json.dumps() it again.
        if isinstance(value, str):
            try:
                # Optional: Verify it's valid JSON, then return it
                json.loads(value) 
                return value
            except ValueError:
                # If valid JSON parsing fails, return empty object to prevent widget crash
                return '{}'

        # If it's a Python Object (from DB), serialize it to JSON
        return json.dumps(value, indent=2)

    def get_context(self, name, value, attrs):
        context = super().get_context(name, value, attrs)
        context['schema_json'] = json.dumps(self.schema)
        # Force the value to go through our robust formatter
        context['widget']['value'] = self.format_value(value)
        return context

    def render(self, name, value, attrs=None, renderer=None):
        context = self.get_context(name, value, attrs)
        return mark_safe(render_to_string(self.template_name, context))