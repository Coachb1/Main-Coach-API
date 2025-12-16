from rest_framework import serializers

from company_iq.models import CompanyIQ


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
