from rest_framework import serializers

from company_iq.models import CompanyIQ
import re

def normalize_list_input(value):
    """
    Accepts:
    - string with bullets/newlines
    - list of strings
    Returns:
    - clean list of strings
    """
    if value is None:
        return []

    # Case 1: string input
    if isinstance(value, str):
        # split by newlines
        lines = re.split(r"[\n\r]+", value)
        cleaned = []
        for line in lines:
            item = line.strip()
            # remove bullets like *, -, •
            item = re.sub(r"^[\*\-\•]+\s*", "", item)
            if item:
                cleaned.append(item)
        return cleaned

    # Case 2: list input
    if isinstance(value, list):
        cleaned = []
        for item in value:
            if isinstance(item, str):
                item = item.strip()
                item = re.sub(r"^[\*\-\•]+\s*", "", item)
                if item:
                    cleaned.append(item)
        return cleaned

    return value


class CompanyIQSerializer(serializers.ModelSerializer):
    class Meta:
        model = CompanyIQ
        fields = [
            "uid",
            "company",
            "company_normalized",
            "industry",
            "hq",
            "revenue_us_millions",
            "employees_full_time",
            "ai_cloud_leadership_roles",
            "ai_digital_initiatives",
            "cloud_tech_stack_signals",
            "ai_use_cases",
            "transformation_iq_outlook",
            "source",
            "approved",
            "created",
            "updated",
        ]
        read_only_fields = ["uid", "company_normalized", "created", "updated"]

    def to_representation(self, instance):
        data = super().to_representation(instance)
        # Normalize list fields in the output
        data["ai_cloud_leadership_roles"] = normalize_list_input(data.get("ai_cloud_leadership_roles"))
        data["ai_digital_initiatives"] = normalize_list_input(data.get("ai_digital_initiatives"))
        data["cloud_tech_stack_signals"] = normalize_list_input(data.get("cloud_tech_stack_signals"))
        data["ai_use_cases"] = normalize_list_input(data.get("ai_use_cases"))
        return data


class ApprovedCompanyIQSerializer(serializers.ModelSerializer):
    """Serializer for listing approved CompanyIQ records"""
    class Meta:
        model = CompanyIQ
        fields = [
            "uid",
            "company",
            "industry",
            "hq",
            "revenue_us_millions",
            "employees_full_time",
            "ai_cloud_leadership_roles",
            "ai_digital_initiatives",
            "cloud_tech_stack_signals",
            "ai_use_cases",
            "transformation_iq_outlook",
            "source",
            "created",
        ]
        read_only_fields = fields
