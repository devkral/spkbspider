# Generated by Django 2.0.6 on 2018-06-18 11:47

from django.db import migrations


class Migration(migrations.Migration):

    dependencies = [
        ('spider_keys', '0001_initial'),
    ]

    operations = [
        migrations.RemoveField(
            model_name='publickey',
            name='hash',
        ),
    ]