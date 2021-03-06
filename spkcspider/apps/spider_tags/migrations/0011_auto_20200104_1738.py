# Generated by Django 3.0.2 on 2020-01-04 17:38

from django.db import migrations


def fix_usertags(apps, schema_editor):
    DataContent = apps.get_model("spider_base", "DataContent")
    TagLayout = apps.get_model("spider_tags", "TagLayout")

    for d in DataContent.objects.filter(
        associated__ctype__name="TagLayout"
    ):
        layout = TagLayout.objects.get(id=d.free_data["tmp_layout_id"])
        layout.usertag = d.associated
        layout.save()
        del d.free_data["tmp_layout_id"]
        d.clean()
        d.save(update_fields=["free_data"])


class Migration(migrations.Migration):

    dependencies = [
        ('spider_tags', '0010_auto_20200104_1737'),
    ]

    operations = [
        migrations.RunPython(fix_usertags),
    ]
