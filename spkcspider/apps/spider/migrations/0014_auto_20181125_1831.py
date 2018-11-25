# Generated by Django 2.1.3 on 2018-11-25 18:31

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('spider_base', '0013_authtoken_extra'),
    ]

    operations = [
        migrations.AlterField(
            model_name='travelprotection',
            name='login_protection',
            field=models.CharField(choices=[('a', 'No Login protection'), ('b', 'Fake login'), ('c', 'Wipe'), ('d', 'Wipe User')], default='a', help_text='\n    No Login Protection: normal, default\n    Fake Login: fake login and index (experimental)\n    Wipe: Wipe protected content,\n    except they are protected by a deletion period\n    Wipe User: destroy user on login\n\n\n    <div>\n        Danger: every option other than: "No Login Protection" can screw you.\n        "Fake Login" can trap you in a parallel reality\n    </div>\n', max_length=10),
        ),
    ]
