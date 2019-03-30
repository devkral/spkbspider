
import logging

from django.utils.html import escape
from django.db import models
from django.utils.translation import gettext, gettext_lazy as _

from django.views.decorators.csrf import csrf_exempt
from django.core.exceptions import ValidationError
from django.contrib.contenttypes.models import ContentType
from django.urls import reverse
from django.http import HttpResponse


from rdflib import URIRef
from jsonfield import JSONField

from spkcspider.apps.spider.contents import (
    BaseContent, add_content, VariantType, ActionUrl
)
from spkcspider.apps.spider.helpers import get_settings_func

from spkcspider.apps.spider.models import AssignedContent

logger = logging.getLogger(__name__)

try:
    from lru import LRU
    CACHE_FORMS = LRU(256)
except Exception:
    logger.warning("LRU dict failed, use dict instead", exc_info=True)
    CACHE_FORMS = {}


# Create your models here.


class TagLayout(models.Model):
    name = models.SlugField(max_length=255, null=False)
    # shall it be unique for a component?
    unique = models.BooleanField(default=False, blank=True)
    layout = JSONField(
        default=list,
        help_text=_("Field list in JSON format")
    )
    default_verifiers = JSONField(default=list, blank=True)
    usertag = models.OneToOneField(
        "spider_tags.UserTagLayout", on_delete=models.CASCADE,
        related_name="layout", null=True, blank=True
    )

    class Meta(object):
        unique_together = [
            ("name", "usertag")
        ]

    def full_clean(self, **kwargs):
        # checked with clean
        kwargs.setdefault("exclude", []).append("usertag")
        return super().full_clean(**kwargs)

    def clean(self):
        if TagLayout.objects.filter(usertag=None, name=self.name).exists():
            raise ValidationError(
                _("Layout exists already"),
                code="unique"
            )
        if self.usertag:
            self.usertag.full_clean(exclude=["layout"])

    def get_form(self):
        compkey = (self.name, self.usertag.pk if self.usertag else None)
        form = CACHE_FORMS.get(compkey)
        if not form:
            from .forms import generate_form
            form = generate_form("LayoutForm", self.layout)
            CACHE_FORMS[compkey] = form
        return form

    def __repr__(self):
        if self.usertag:
            return "<TagLayout: %s:%s>" % (
                self.name, self.usertag.associated.usercomponent.user
            )
        return "<TagLayout: %s>" % self.name

    def __str__(self):
        if self.usertag:
            return "TagLayout: %s:%s" % (
                self.name, self.usertag.associated.usercomponent.user
            )
        return "TagLayout: %s" % self.name

    def save(self, *args, **kwargs):
        if self.pk:
            # invalidate forms
            old = TagLayout.objects.get(pk=self.pk)
            _id = self.usertag.pk if self.usertag else None
            try:
                del CACHE_FORMS[old.name, _id]
            except KeyError:
                pass
        return super().save(*args, **kwargs)


@add_content
class UserTagLayout(BaseContent):
    # 10 is required for preventing info leak gadgets via component auth
    appearances = [
        {
            "name": "TagLayout",
            "ctype": VariantType.unique.value,
            "strength": 10
        }
    ]

    def __str__(self):
        if not self.id:
            return self.localize_name("UserTagLayout")
        return "%s: %s:%s" % (
            self.localize_name("UserTagLayout"),
            self.layout.name,
            self.associated.usercomponent.user
        )

    def __repr__(self):
        if not self.id:
            return self.localize_name("UserTagLayout")
        return "<%s: %s:%s>" % (
            self.localize_name("UserTagLayout"),
            self.layout.name,
            self.associated.usercomponent.user
        )

    def get_size(self):
        return len(str(self.layout.layout).encode("utf8"))

    def get_template_name(self, scope):
        if scope == "view":
            return 'spider_tags/edit_preview_form.html'
        return super().get_template_name(scope)

    def get_strength_link(self):
        # never allow links to this, elsewise with links is an information
        # disclosure possible
        return 11

    def get_info(self):
        return "%slayout=%s\n" % (
            super().get_info(),
            self.layout.name
        )

    def get_form(self, scope):
        if scope in {"add", "update"}:
            from .forms import TagLayoutForm
            return TagLayoutForm
        else:
            return self.layout.get_form()

    def access_view(self, **kwargs):
        _ = gettext
        kwargs.setdefault(
            "legend",
            escape(_("Check \"%s\"") % self.__str__())
        )
        # not visible by default
        kwargs.setdefault("confirm", _("Check"))
        # prevent second button
        kwargs.setdefault("inner_form", False)
        return super().access_view(**kwargs)

    def access_add(self, **kwargs):
        if not hasattr(self, "layout"):
            self.layout = TagLayout(usertag=self)
        return super().access_add(**kwargs)

    def get_form_kwargs(self, **kwargs):
        kwargs["instance"] = self.layout
        return super().get_form_kwargs(**kwargs)

    def access(self, context):
        if context["scope"] == "view":
            context["extra_outer_forms"] = ["request_verification_form"]
        return super().access(context)


@add_content
class SpiderTag(BaseContent):
    _cached_references = None
    tmp_primary_anchor = None
    appearances = [
        {
            "name": "SpiderTag",
            "strength": 0,
            "ctype": VariantType.domain_mode
        },
        {
            "name": "PushedTag",
            "strength": 2,
            "ctype": VariantType.component_feature + VariantType.domain_mode
        }
    ]
    layout = models.ForeignKey(
        TagLayout, related_name="tags", on_delete=models.PROTECT,

    )
    tagdata = JSONField(default=dict, blank=True)
    verified_by = JSONField(default=list, blank=True)
    updateable_by = models.ManyToManyField(
        "spider_base.ReferrerObject", related_name="tags", blank=True
    )
    primary = models.BooleanField(default=False, blank=True)

    def __str__(self):
        if not self.id:
            return self.localize_name(self.associated.ctype.name)
        if not self.layout.usertag:
            return "%s: <%s>: %s" % (
                self.localize_name("Tag"),
                self.layout.name,
                self.associated.id
            )
        return "%s: <%s: %s>: %s" % (
            self.localize_name("Tag"),
            self.layout.name,
            self.layout.id,
            self.associated.id
        )

    @classmethod
    def feature_urls(cls):
        return [
            ActionUrl(reverse("spider_tags:create-pushtag"), "pushtag")
        ]

    def get_template_name(self, scope):
        if scope == "update":
            return 'spider_tags/edit_form.html'
        if scope == "push_update":
            return 'spider_base/edit_form.html'
        return super().get_template_name(scope)

    def get_size(self):
        return len(str(self.tagdata).encode("utf8"))

    def get_strength_link(self):
        return 0

    def get_abilities(self, context):
        _abilities = set()
        if (
            context["request"].auth_token and
            context["request"].auth_token.referrer
        ):
            if get_settings_func(
                "SPIDER_TAG_VERIFIER_VALIDATOR",
                "spkcspider.apps.spider.functions.clean_verifier"
            )(self, context["request"]):
                _abilities.add("verify")
            if self.updateable_by.filter(
                id=context["request"].auth_token.referrer.id
            ).exists():
                _abilities.add("push_update")

        return _abilities

    def map_data(self, name, field, data, graph, context):
        if (
            field.__class__.__name__ == "AnchorField" and
            field.use_default_anchor
        ):
            if data is None:
                return URIRef(self.get_primary_anchor())
        return super().map_data(name, field, data, graph, context)

    @csrf_exempt
    def access_verify(self, **kwargs):
        # full url to result
        verified = kwargs["request"].POST.get("url", "")
        if "://" not in verified:
            return HttpResponse("invalid url", status=400)
        if verified in self.verified_by:
            return self.access_view(**kwargs)
        self.verified_by.append(verified)
        self.clean()
        self.save()

        return self.access_view(**kwargs)

    def access_push_update(self, **kwargs):
        kwargs["legend"] = escape(
            _("Update \"%s\" (push)") % self.__str__()
        )
        kwargs["inner_form"] = False
        return self.access_update(**kwargs)

    def access(self, context):
        if context["scope"] not in {"add", "view"}:
            context["extra_outer_forms"] = ["request_verification_form"]
        return super().access(context)

    def get_form(self, scope):
        from .forms import SpiderTagForm
        if scope == "add":
            return SpiderTagForm
        else:
            return self.layout.get_form()

    def get_references(self):
        if not getattr(self, "layout", None):
            return []
        if self._cached_references:
            return self._cached_references
        _cached_references = []
        form = self.layout.get_form()(
            initial=self.tagdata.copy(),
            instance=self,
            uc=self.associated.usercomponent
        )
        attached_to_primary_anchor = False
        for name, field in form.fields.items():
            raw_value = form.initial.get(name, None)
            value = field.to_python(raw_value)
            # e.g. anchors
            if isinstance(value, AssignedContent):
                _cached_references.append(value)
            if (
                field.__class__.__name__ == "AnchorField" and
                field.use_default_anchor
            ):
                if value is None:
                    attached_to_primary_anchor = True

            if issubclass(type(value), BaseContent):
                _cached_references.append(value.associated)

            # e.g. anchors
            if isinstance(value, models.QuerySet):
                if issubclass(value.model, AssignedContent):
                    _cached_references += list(value)

                if issubclass(value.model, BaseContent):
                    _cached_references += list(
                        AssignedContent.objects.filter(
                            object_id__in=value.values_list(
                                "id", flat=True
                            ),
                            content_type=ContentType.objects.get_for_model(
                                value.model
                            )
                        )
                    )
        if (
            attached_to_primary_anchor and
            self.associated.usercomponent.primary_anchor
        ):
            _cached_references.append(
                self.associated.usercomponent.primary_anchor
            )
        if (
            self.associated.attached_to_primary_anchor !=
            attached_to_primary_anchor
        ):
            self.associated.attached_to_primary_anchor = \
                attached_to_primary_anchor
            self.associated.save(
                update_fields=[
                    "attached_to_primary_anchor"
                ]
            )
        self._cached_references = _cached_references
        return self._cached_references

    def get_form_kwargs(self, instance=None, **kwargs):
        if kwargs["scope"] == "add":
            ret = super().get_form_kwargs(
                instance=instance,
                **kwargs
            )
            ret["user"] = self.associated.usercomponent.user
        else:
            ret = super().get_form_kwargs(
                **kwargs
            )
            ret["initial"] = self.tagdata.copy()
            ret["uc"] = self.associated.usercomponent
        return ret

    def encode_verifiers(self):
        return "".join(
            map(
                lambda x: "verified_by={}\n".format(
                    x.replace("\n", "%0A")
                ),
                self.verified_by
            )
        )

    def get_info(self):
        return "{}{}tag={}\n".format(
            super().get_info(unique=self.primary, unlisted=False),
            self.encode_verifiers(),
            self.layout.name
        )
