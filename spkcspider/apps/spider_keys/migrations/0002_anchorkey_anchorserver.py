# Generated by Django 2.1 on 2018-08-24 04:30

from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):

    dependencies = [
        ('spider_keys', '0001_initial'),
    ]

    operations = [
        migrations.CreateModel(
            name='AnchorServer',
            fields=[
                ('id', models.BigAutoField(editable=False, primary_key=True, serialize=False)),
            ],
            options={
                'abstract': False,
                'default_permissions': [],
            },
        ),
        migrations.CreateModel(
            name='AnchorKey',
            fields=[
                ('anchorserver_ptr', models.OneToOneField(auto_created=True, on_delete=django.db.models.deletion.CASCADE, parent_link=True, primary_key=True, serialize=False, to='spider_keys.AnchorServer')),
                ('signature', models.CharField(help_text="""Signature of Identifier (base64-encoded)""", max_length=1024)),
                ('key', models.ForeignKey(help_text=""""Public Key"-Content""", on_delete=django.db.models.deletion.CASCADE, related_name='+', to='spider_keys.PublicKey')),
            ],
            options={
                'abstract': False,
                'default_permissions': [],
            },
            bases=('spider_keys.anchorserver',),
        ),
    ]
