# Generated by Django 2.1.5 on 2019-01-09 19:27

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('spider_base', '0006_assignedcontent_priority'),
    ]

    operations = [
        migrations.AddField(
            model_name='linkcontent',
            name='push',
            field=models.BooleanField(blank=True, default=False, help_text='Push Link to top.'),
        ),
    ]
