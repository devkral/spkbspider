# Generated by Django 2.2.1 on 2019-05-14 18:53

from django.db import migrations


class Migration(migrations.Migration):

    dependencies = [
        ('spider_base', '0023_auto_20190513_1506'),
    ]

    operations = [
        migrations.AlterModelOptions(
            name='travelprotection',
            options={'default_permissions': (), 'permissions': [('approve_travelprotection', 'Can approve dangerous TravelProtections')]},
        ),
    ]