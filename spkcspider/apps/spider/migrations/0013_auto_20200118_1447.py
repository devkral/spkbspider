# Generated by Django 3.0.2 on 2020-01-18 14:47

from django.db import migrations, models
import django.db.models.deletion
import django.db.models.expressions
import jsonfield.fields


class Migration(migrations.Migration):

    dependencies = [
        ('spider_base', '0012_auto_20191230_1305'),
    ]

    operations = [
        migrations.CreateModel(
            name='SmartTag',
            fields=[
                ('id', models.BigAutoField(editable=False, primary_key=True, serialize=False)),
                ('name', models.CharField(blank=True, default='', max_length=50)),
                ('unique', models.BooleanField(blank=True, default=False)),
                ('created', models.DateTimeField(auto_now_add=True)),
                ('modified', models.DateTimeField(auto_now=True)),
                ('data', jsonfield.fields.JSONField(blank=True, default=dict)),
                ('free', models.BooleanField(default=False, editable=False)),
                ('content', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='smarttags', to='spider_base.AssignedContent')),
                ('target', models.ForeignKey(null=True, on_delete=django.db.models.deletion.CASCADE, related_name='smarttag_sources', to='spider_base.AssignedContent')),
            ],
        ),
        migrations.AddConstraint(
            model_name='smarttag',
            constraint=models.UniqueConstraint(condition=models.Q(unique=True), fields=('content', 'target', 'name'), name='smarttag_target_unique'),
        ),
        migrations.AddConstraint(
            model_name='smarttag',
            constraint=models.UniqueConstraint(condition=models.Q(('target__isnull', True), ('unique', True)), fields=('content', 'name'), name='smarttag_notarget_unique'),
        ),
        migrations.AddConstraint(
            model_name='smarttag',
            constraint=models.CheckConstraint(check=models.Q(_negated=True, content=django.db.models.expressions.F('target')), name='smarttag_content_not_target'),
        ),
    ]