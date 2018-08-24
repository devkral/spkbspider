__all__ = ["valid_fields", "generate_fields"]

import logging
from django import forms
from django.apps import apps
from django.utils.translation import gettext

from spkcspider.apps.spider.constants import UserContentType

valid_fields = {}

safe_default_fields = [
    "BooleanField", "CharField", "ChoiceField", "MultipleChoiceField",
    "DateField", "DateTimeField", "DecimalField", "DurationField",
    "EmailField", "FilePathField", "FloatField", "GenericIPAddressField",
    "ModelChoiceField", "ModelMultipleChoiceField", "SlugField", "TimeField",
    "URLField"
]
for i in safe_default_fields:
    valid_fields[i] = getattr(forms, i)


class TextareaField(forms.CharField):
    widget = forms.Textarea
valid_fields["TextareaField"] = TextareaField  # noqa: E305

# extra attributes for fields:
# limit_to_usercomponent = "<fieldname">: limit field name to associated uc
# limit_to_user = "<fieldname">: limit field name to user of associated uc


def localized_choices(obj):
    def func(*, choices=(), **kwargs):
        choices = map(lambda x: (x[0], gettext(x[1])), choices)
        return obj(choices=choices, **kwargs)
    return func


valid_fields["LocalizedChoiceField"] = localized_choices(forms.ChoiceField)


valid_fields["MultipleLocalizedChoiceField"] = \
    localized_choices(forms.MultipleChoiceField)


class UserContentRefField(forms.ModelChoiceField):
    embed_content = None

    # limit_to_uc: limit to usercomponent, if False to user
    def __init__(self, modelname, limit_to_uc=True, embed=False, **kwargs):
        from spkcspider.apps.spider.contents import BaseContent
        self.embed_content = embed
        if limit_to_uc:
            self.limit_to_usercomponent = "associated_rel__usercomponent"
        else:
            self.limit_to_user = "associated_rel__usercomponent__user"

        model = apps.get_model(
            modelname
        )
        if not issubclass(model, BaseContent):
            raise Exception("Not a content (inherit from BaseContent)")

        kwargs["queryset"] = model.objects.filter(
            **kwargs.pop("limit_choices_to", {})
        )
        super().__init__(**kwargs)
valid_fields["UserContentRefField"] = UserContentRefField  # noqa: E305


class MultipleUserContentRefField(forms.ModelMultipleChoiceField):
    embed_content = None

    # limit_to_uc: limit to usercomponent, if False to user
    def __init__(self, modelname, limit_to_uc=True, embed=False, **kwargs):
        from spkcspider.apps.spider.contents import BaseContent
        self.embed_content = embed
        if limit_to_uc:
            self.limit_to_usercomponent = "associated_rel__usercomponent"
        else:
            self.limit_to_user = "associated_rel__usercomponent__user"

        model = apps.get_model(
            modelname
        )
        if not issubclass(model, BaseContent):
            raise Exception("Not a content (inherit from BaseContent)")

        kwargs["queryset"] = model.objects.filter(
            **kwargs.pop("limit_choices_to", {})
        )
        super().__init__(**kwargs)
valid_fields["MultipleUserContentRefField"] = MultipleUserContentRefField  # noqa: E305, E501


class AnchorField(forms.ModelChoiceField):
    embed_content = True

    # limit_to_uc: limit to usercomponent, if False to user
    def __init__(self, limit_to_uc=True, **kwargs):
        from spkcspider.apps.spider.models import AssignedContent
        if limit_to_uc:
            self.limit_to_usercomponent = "usercomponent"
        else:
            self.limit_to_user = "usercomponent__user"

        kwargs["queryset"] = AssignedContent.objects.filter(
            ctype__ctype__contains=UserContentType.anchor.value,
            **kwargs.pop("limit_choices_to", {})
        )
        super().__init__(**kwargs)

    def label_from_instance(self, obj):
        return str(obj.content)

    def to_python(self, value):
        if value in self.empty_values:
            return None
        try:
            key = self.to_field_name or 'pk'
            value = self.queryset.get(**{key: value}).content
        except (ValueError, TypeError, self.queryset.model.DoesNotExist):
            raise forms.ValidationError(
                self.error_messages['invalid_choice'], code='invalid_choice'
            )
        return value
valid_fields["AnchorField"] = AnchorField  # noqa: E305, E501


def generate_fields(layout, prefix="", _base=None, _mainprefix=None):
    if not _base:
        _base = []
        _mainprefix = prefix
    for i in layout:
        item = i.copy()
        key, field = item.pop("key", None), item.pop("field", None)
        localize = item.pop("localize", False)
        if "label" not in item:
            item["label"] = key.replace(_mainprefix, "", 1)

        if localize:
            item["label"] = gettext(item["label"])
            if "help_text" in item:
                item["help_text"] = gettext(item["help_text"])
        # readd prefix to label:
        item["label"] = "".join(
                [
                    # remove mainprefix
                    *prefix.replace(
                        _mainprefix, "", 1
                    ).replace(":", ": "),  # beautify :
                    item["label"],
                ]
            )
        if not key or ":" in key:
            logging.warning("Invalid item (no key/contains :)", i)
            continue
        if isinstance(field, list):
            new_prefix = "{}:{}".format(prefix, key)
            generate_fields(
                field, new_prefix, _base=_base, _mainprefix=_mainprefix
            )
        elif isinstance(field, str):
            new_field = valid_fields.get(field)
            if not new_field:
                logging.warning("Invalid field specified: %s", field)
            else:
                _base.append(("{}:{}".format(prefix, key), new_field(**item)))
        else:
            logging.warning("Invalid item", i)
    return _base
