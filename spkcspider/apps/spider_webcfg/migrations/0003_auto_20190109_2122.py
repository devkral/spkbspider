# Generated by Django 2.1.5 on 2019-01-09 21:22

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('spider_webcfg', '0002_webconfig_creation_url'),
    ]

    operations = [
        migrations.AlterField(
            model_name='webconfig',
            name='url',
            field=models.URLField(max_length=400),
        ),
    ]
