# Generated by Django 2.1 on 2018-08-30 13:52

import datetime
from django.conf import settings
from django.db import migrations, models
import django.db.models.deletion
import jsonfield.fields
import spkcspider.apps.spider.helpers
import spkcspider.apps.spider.models.content_base
import spkcspider.apps.spider.models.base
import spkcspider.apps.spider.models.protections


class Migration(migrations.Migration):

    initial = True

    dependencies = [
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
        ('contenttypes', '0002_remove_content_type_name'),
    ]

    operations = [
        migrations.CreateModel(
            name='AssignedContent',
            fields=[
                ('id', models.BigAutoField(editable=False, primary_key=True, serialize=False)),
                ('nonce', models.SlugField(db_index=False, default=spkcspider.apps.spider.helpers.create_b64_token, max_length=120)),
                ('created', models.DateTimeField(auto_now_add=True)),
                ('modified', models.DateTimeField(auto_now=True)),
                ('deletion_requested', models.DateTimeField(blank=True, default=None, null=True)),
                ('info', models.TextField(editable=False, validators=[spkcspider.apps.spider.models.base.info_field_validator])),
                ('object_id', models.BigIntegerField(editable=False)),
                ('content_type', models.ForeignKey(editable=False, on_delete=django.db.models.deletion.CASCADE, to='contenttypes.ContentType')),
            ],
        ),
        migrations.CreateModel(
            name='AssignedProtection',
            fields=[
                ('id', models.BigAutoField(primary_key=True, serialize=False)),
                ('data', jsonfield.fields.JSONField(default=dict)),
                ('created', models.DateTimeField(auto_now_add=True)),
                ('modified', models.DateTimeField(auto_now=True)),
                ('active', models.BooleanField(default=True)),
                ('instant_fail', models.BooleanField(default=False, help_text='Auth fails if test fails, stronger than required_passes\nWorks even if required_passes=0\nDoes not contribute to required_passes, ideal for side effects')),
            ],
        ),
        migrations.CreateModel(
            name='AuthToken',
            fields=[
                ('id', models.BigAutoField(editable=False, primary_key=True, serialize=False)),
                ('session_key', models.CharField(max_length=40, null=True)),
                ('token', models.SlugField(max_length=136)),
                ('created', models.DateTimeField(auto_now_add=True)),
            ],
        ),
        migrations.CreateModel(
            name='ContentVariant',
            fields=[
                ('id', models.BigAutoField(editable=False, primary_key=True, serialize=False)),
                ('ctype', models.CharField(max_length=10)),
                ('code', models.CharField(max_length=255)),
                ('name', models.SlugField(max_length=255, unique=True)),
            ],
        ),
        migrations.CreateModel(
            name='LinkContent',
            fields=[
                ('id', models.BigAutoField(editable=False, primary_key=True, serialize=False)),
                ('content', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='+', to='spider_base.AssignedContent')),
            ],
            options={
                'abstract': False,
                'default_permissions': (),
            },
        ),
        migrations.CreateModel(
            name='Protection',
            fields=[
                ('code', models.SlugField(db_index=False, max_length=10, primary_key=True, serialize=False)),
                ('ptype', models.CharField(default='b', max_length=10)),
            ],
        ),
        migrations.CreateModel(
            name='UserComponent',
            fields=[
                ('id', models.BigAutoField(editable=False, primary_key=True, serialize=False)),
                ('nonce', models.SlugField(db_index=False, default=spkcspider.apps.spider.helpers.create_b64_token, max_length=120)),
                ('public', models.BooleanField(default=False, help_text=(
                    "Is public? Is listed and searchable?<br/>"
                    "Note: This field is maybe not deactivatable"
                    "because of assigned content"
                ))),
                ('required_passes', models.PositiveIntegerField(default=0, help_text='How many protection must be passed? Set greater 0 to enable protection based access')),
                ('name', models.SlugField(db_index=False, help_text='\nName of the component.<br/>\nNote: there are special named components\nwith different protection types and scopes.<br/>\nMost prominent: "index" for authentication\n')),
                ('created', models.DateTimeField(auto_now_add=True)),
                ('modified', models.DateTimeField(auto_now=True)),
                ('token_duration', models.DurationField(default=datetime.timedelta(7))),
                ('deletion_requested', models.DateTimeField(default=None, null=True)),
                ('user', models.ForeignKey(editable=False, on_delete=django.db.models.deletion.CASCADE, to=settings.AUTH_USER_MODEL)),
            ],
        ),
        migrations.CreateModel(
            name='UserInfo',
            fields=[
                ('id', models.BigAutoField(editable=False, primary_key=True, serialize=False)),
                ('used_space', models.BigIntegerField(default=0, editable=False)),
                ('allowed_content', models.ManyToManyField(editable=False, related_name='_userinfo_allowed_content_+', to='spider_base.ContentVariant')),
                ('user', models.OneToOneField(editable=False, on_delete=django.db.models.deletion.CASCADE, related_name='spider_info', to=settings.AUTH_USER_MODEL)),
            ],
            options={
                'default_permissions': (),
            },
        ),
        migrations.AddField(
            model_name='authtoken',
            name='usercomponent',
            field=models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='authtokens', to='spider_base.UserComponent'),
        ),
        migrations.AddField(
            model_name='assignedprotection',
            name='protection',
            field=models.ForeignKey(editable=False, limit_choices_to=spkcspider.apps.spider.models.protections.get_limit_choices_assigned_protection, on_delete=django.db.models.deletion.CASCADE, related_name='assigned', to='spider_base.Protection'),
        ),
        migrations.AddField(
            model_name='assignedprotection',
            name='usercomponent',
            field=models.ForeignKey(editable=False, on_delete=django.db.models.deletion.CASCADE, related_name='protections', to='spider_base.UserComponent'),
        ),
        migrations.AddField(
            model_name='assignedcontent',
            name='ctype',
            field=models.ForeignKey(editable=False, null=True, on_delete=django.db.models.deletion.SET_NULL, to='spider_base.ContentVariant'),
        ),
        migrations.AddField(
            model_name='assignedcontent',
            name='usercomponent',
            field=models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='contents', to='spider_base.UserComponent'),
        ),
        migrations.AlterUniqueTogether(
            name='usercomponent',
            unique_together={('user', 'name')},
        ),
        migrations.AlterUniqueTogether(
            name='authtoken',
            unique_together={('usercomponent', 'token')},
        ),
        migrations.AlterUniqueTogether(
            name='assignedprotection',
            unique_together={('protection', 'usercomponent')},
        ),
    ]

    operations.append(
        migrations.AlterUniqueTogether(
            name='assignedcontent',
            unique_together={('content_type', 'object_id')},
        )
    )
