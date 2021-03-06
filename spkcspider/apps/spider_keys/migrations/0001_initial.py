# Generated by Django 2.1 on 2018-08-10 00:34

import spkcspider.apps.spider_keys.models
import spkcspider.apps.spider_keys.forms
from django.db import migrations, models


class Migration(migrations.Migration):

    initial = True

    dependencies = [
    ]

    operations = [
        migrations.CreateModel(
            name='PublicKey',
            fields=[
                ('id', models.BigAutoField(editable=False, primary_key=True, serialize=False)),
                ('key', models.TextField(validators=[
                 spkcspider.apps.spider_keys.forms.valid_pkey_properties])),
                ('note', models.TextField(blank=True, default='', max_length=100)),
            ],
            options={
                'abstract': False,
                'default_permissions': (),
            },
        ),
    ]
