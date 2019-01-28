# Generated by Django 2.1.5 on 2019-01-28 13:49

from django.db import migrations


def move_tokens_forward(apps, schema_editor):
    AssignedContent = apps.get_model('spider_base', 'AssignedContent')
    UserComponent = apps.get_model('spider_base', 'UserComponent')
    for row in AssignedContent.objects.all():
        if row.nonce:
            row.token = '%s/%s' % (row.id, row.nonce)
        row.nonce = None
        row.save()
    for row in UserComponent.objects.all():
        if row.nonce:
            row.token = '%s/%s' % (row.id, row.nonce)
        row.nonce = None
        row.save()


def move_tokens_back(apps, schema_editor):
    AssignedContent = apps.get_model('spider_base', 'AssignedContent')
    UserComponent = apps.get_model('spider_base', 'UserComponent')
    for row in AssignedContent.objects.all():
        if "/" in row.token:
            row.nonce = row.token.split("/", 1)[1]
        else:
            row.nonce = row.token.split("_", 1)[1]
        row.save()
    for row in UserComponent.objects.all():
        if "/" in row.token:
            row.nonce = row.token.split("/", 1)[1]
        else:
            row.nonce = row.token.split("_", 1)[1]
        row.save()


class Migration(migrations.Migration):

    dependencies = [
        ('spider_base', '0003_auto_20190128_1339'),
    ]

    operations = [
        migrations.RunPython(move_tokens_forward, move_tokens_back),
    ]
