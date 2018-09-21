# Generated by Django 2.1.1 on 2018-09-19 23:59

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('spider_base', '0003_auto_20180918_1138'),
    ]

    operations = [
        migrations.AlterModelOptions(
            name='usercomponent',
            options={'permissions': [('can_feature', 'Can feature User Components')]},
        ),
        migrations.AddField(
            model_name='usercomponent',
            name='featured',
            field=models.BooleanField(default=False, help_text='Appears as featured on "home" page'),
        ),
    ]