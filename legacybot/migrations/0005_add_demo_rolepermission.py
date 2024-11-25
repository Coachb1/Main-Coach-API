# migrations/000X_add_demo_role.py
from django.db import migrations

def create_demo_role(apps, schema_editor):
    LegacyBotRoleAndPermissions = apps.get_model('legacybot', 'LegacyBotRoleAndPermissions')
    LegacyBotRoleAndPermissions.objects.get_or_create(role='demo')

class Migration(migrations.Migration):
    dependencies = [
        ('legacybot', '0004_legacybot_bot_identifier_legacybot_creator_and_more'),
    ]

    operations = [
        migrations.RunPython(create_demo_role),
    ]
