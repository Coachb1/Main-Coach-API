from rest_framework import serializers

from company_iq.models import CompanyIQ
from company_iq.services.csv_upload import parse_list


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
            "sticker"
        ]
        read_only_fields = ["uid", "company_normalized", "created", "updated"]

    def to_representation(self, instance):
        data = super().to_representation(instance)
        # Normalize list fields in the output
        data["ai_cloud_leadership_roles"] = parse_list(data.get("ai_cloud_leadership_roles"))
        data["ai_digital_initiatives"] = parse_list(data.get("ai_digital_initiatives"))
        data["cloud_tech_stack_signals"] = parse_list(data.get("cloud_tech_stack_signals"))
        data["ai_use_cases"] = parse_list(data.get("ai_use_cases"))
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
            "sticker"
        ]
        read_only_fields = fields


    def to_representation(self, instance):
        data = super().to_representation(instance)
        # Normalize list fields in the output
        data["ai_cloud_leadership_roles"] = parse_list(data.get("ai_cloud_leadership_roles"))
        data["ai_digital_initiatives"] = parse_list(data.get("ai_digital_initiatives"))
        data["cloud_tech_stack_signals"] = parse_list(data.get("cloud_tech_stack_signals"))
        data["ai_use_cases"] = parse_list(data.get("ai_use_cases"))
        return data
