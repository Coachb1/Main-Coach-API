# migrations/000Y_set_default_role.py
from django.db import migrations

def set_default_role(apps, schema_editor):
    LegacyBotUser = apps.get_model('legacybot', 'LegacyBotUser')
    LegacyBotRoleAndPermissions = apps.get_model('legacybot', 'LegacyBotRoleAndPermissions')
    demo_role = LegacyBotRoleAndPermissions.objects.get(role='demo')
    
    LegacyBotUser.objects.filter(role__isnull=True).update(role=demo_role)

class Migration(migrations.Migration):
    dependencies = [
        ('legacybot', '0005_add_demo_rolepermission'),  # Ensure this runs after the demo role is created
    ]

    operations = [
        migrations.RunPython(set_default_role),
    ]
