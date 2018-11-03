__all__ = ["FileForm", "TextForm", "RawTextForm"]


import bleach
from bleach import sanitizer

from django.conf import settings
from django import forms

from spkcspider.apps.spider.helpers import get_settings_func
from .models import FileFilet, TextFilet

tags = sanitizer.ALLOWED_TAGS + ['img', 'p', 'br', 'sub', 'sup']
protocols = sanitizer.ALLOWED_PROTOCOLS + ['data']


class FakeList(object):
    def __contains__(self, value):
        return True


styles = FakeList()
svg_props = FakeList()
_extra = '' if settings.DEBUG else '.min'


def check_attrs_func(tag, name, value):
    # currently no objections
    return True


class FileForm(forms.ModelForm):
    user = None
    MAX_FILE_SIZE = forms.CharField(
        disabled=True, widget=forms.HiddenInput(), required=False
    )

    class Meta:
        model = FileFilet
        fields = ['file', 'name']

    def __init__(self, request, **kwargs):
        super().__init__(**kwargs)
        self.fields['name'].required = False
        if request.is_owner:
            self.user = request.user
            return
        self.fields["file"].editable = False
        self.fields["name"].editable = False
        if request.user.is_staff or request.user.is_superuser:
            self.fields["MAX_FILE_SIZE"].initial = getattr(
                settings, "MAX_FILE_SIZE", None
            )
        else:
            self.fields["MAX_FILE_SIZE"].initial = getattr(
                settings, "MAX_FILE_SIZE_STAFF", None
            )
        if not self.fields["MAX_FILE_SIZE"].initial:
            del self.fields["MAX_FILE_SIZE"]

    def clean(self):
        ret = super().clean()
        if "file" not in ret:
            return ret
        if not ret["name"] or ret["name"].strip() == "":
            ret["name"] = ret["file"].name
        # has to raise ValidationError
        get_settings_func(
            "UPLOAD_FILTER_FUNC",
            "spkcspider.apps.spider.functions.allow_all_filter"
        )(ret["file"])
        return ret


class TextForm(forms.ModelForm):
    class Meta:
        model = TextFilet
        fields = ['text', 'name', 'editable_from', 'preview_words']

    class Media:
        css = {
            'all': [
                'node_modules/trumbowyg/dist/ui/trumbowyg.min.css',
                'node_modules/trumbowyg/dist/plugins/colors/ui/trumbowyg.colors.css',  # noqa: E501
                'spider_base/trumbowyg.css',
                # 'node_modules/trumbowyg/dist/plugins/history/ui/trumbowyg.history.css'  # noqa: E501
            ]
        }
        js = [
            'admin/js/vendor/jquery/jquery%s.js' % _extra,
            'node_modules/trumbowyg/dist/trumbowyg%s.js' % _extra,
            'node_modules/trumbowyg/dist/plugins/pasteimage/trumbowyg.pasteimage.min.js',  # noqa: E501
            'node_modules/trumbowyg/dist/plugins/base64/trumbowyg.base64.min.js',  # noqa: E501
            'node_modules/trumbowyg/dist/plugins/history/trumbowyg.history.min.js',  # noqa: E501
            'node_modules/trumbowyg/dist/plugins/colors/trumbowyg.colors.min.js',  # noqa: E501
            'spider_filets/text.js'
        ]

    def __init__(self, request, source=None, **kwargs):
        super().__init__(**kwargs)
        self.fields["editable_from"].to_field_name = "name"
        if request.is_owner:
            self.fields["editable_from"].queryset = \
                self.fields["editable_from"].queryset.filter(
                    user=request.user
                ).exclude(name__in=("index", "fake_index"))
            return

        del self.fields["editable_from"]
        self.fields["preview_words"].disabled = True
        self.fields["name"].disabled = True

        allow_edit = False
        if self.instance.editable_from.filter(
            pk=source.pk
        ).exists():
            if request.is_elevated_request:
                allow_edit = True

        self.fields["text"].disabled = not allow_edit

    def clean_text(self):
        return bleach.clean(
            self.cleaned_data['text'],
            tags=tags,
            attributes=check_attrs_func,
            protocols=protocols,
            styles=styles,
        )


class RawTextForm(forms.ModelForm):
    class Meta:
        model = TextFilet
        fields = ['text', 'name']

    def __init__(self, request, source=None, **kwargs):
        super().__init__(**kwargs)
