# -*- coding: utf-8 -*-
# Generated by Django 1.11.7 on 2017-11-13 08:43
from __future__ import unicode_literals

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('spiderucs', '0002_auto_20171112_1920'),
    ]

    operations = [
        migrations.RemoveField(
            model_name='protection',
            name='can_render',
        ),
        migrations.AddField(
            model_name='protection',
            name='skip_render',
            field=models.BooleanField(default=True),
        ),
    ]