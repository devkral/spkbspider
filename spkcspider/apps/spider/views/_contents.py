""" Content Views """

__all__ = (
    "ContentIndex", "ContentAdd", "ContentAccess", "ContentRemove"
)

from django.views.generic.edit import DeleteView, UpdateView, CreateView
from django.views.generic.list import ListView
from django.shortcuts import get_object_or_404, redirect
from django.urls import reverse
from django.http.response import HttpResponseBase, HttpResponse
from django.db import models
from django.conf import settings
from django.core.exceptions import PermissionDenied
from django.http import Http404


from rdflib import Graph, Literal, URIRef, XSD


from ._core import UCTestMixin, EntityDeletionMixin, ReferrerMixin
from ..models import (
    AssignedContent, ContentVariant, UserComponent
)
from ..forms import UserContentForm
from ..helpers import get_settings_func, add_property
from ..constants.static import spkcgraph, VariantType
from ..serializing import paginate_stream, serialize_stream


class ContentBase(UCTestMixin):
    model = AssignedContent
    scope = None
    object = None
    # use nonce of content object instead
    no_nonce_usercomponent = True

    def dispatch(self, request, *args, **kwargs):
        try:
            return super().dispatch(request, *args, **kwargs)
        except Http404:
            return get_settings_func(
                "RATELIMIT_FUNC",
                "spkcspider.apps.spider.functions.rate_limit_default"
            )(self, request)

    def get_template_names(self):
        if self.scope in ("add", "update"):
            return ['spider_base/assignedcontent_form.html']
        elif self.scope == "list":
            return ['spider_base/assignedcontent_list.html']
        else:
            return ['spider_base/assignedcontent_access.html']

    def get_ordering(self, issearching=False):
        if self.scope != "list":
            # export: also serializer, other scopes: only one object, overhead
            return None
        # ordering will happen in serializer
        if "raw" in self.request.GET:
            return None
        return ("-priority", "-modified")

    def get_context_data(self, **kwargs):
        kwargs["request"] = self.request
        kwargs["scope"] = self.scope
        kwargs["uc"] = self.usercomponent
        kwargs["enctype"] = "multipart/form-data"
        return super().get_context_data(**kwargs)

    def get_queryset(self):
        ret = self.model.objects.all()
        # skip search if user and single object
        if self.scope in ("add", "update", "update_raw"):
            return ret

        searchq = models.Q()
        searchq_exc = models.Q()

        counter = 0
        # against ddos
        max_counter = getattr(settings, "MAX_SEARCH_PARAMETERS", 60)

        searchlist = []
        idlist = []

        if getattr(self.request, "auth_token", None):
            idlist += self.request.auth_token.extra.get("ids", [])
            searchlist += self.request.auth_token.extra.get("filter", [])


        if self.scope == "list":
            if "search" in self.request.POST or "id" in self.request.POST:
                searchlist += self.request.POST.getlist("search")
                idlist += self.request.POST.getlist("id")
            else:
                searchlist += self.request.GET.getlist("search")
                idlist += self.request.GET.getlist("id")
        elif self.scope not in ("add", "update", "update_raw"):
            searchlist += self.request.GET.getlist("search")

        for item in searchlist:
            if counter > max_counter:
                break
            counter += 1
            if len(item) == 0:
                continue
            use_info = False
            if item.startswith("!!"):
                _item = item[1:]
            elif item.startswith("__"):
                _item = item[1:]
            elif item.startswith("!_"):
                _item = item[2:]
                use_info = True
            elif item.startswith("!"):
                _item = item[1:]
            elif item.startswith("_"):
                _item = item[1:]
                use_info = True
            else:
                _item = item
            if use_info:
                qob = models.Q(info__contains="\n%s\n" % _item)
            else:
                qob = models.Q(
                    info__icontains=_item
                )
            if item.startswith("!!"):
                searchq |= qob
            elif item.startswith("!"):
                searchq_exc |= qob
            else:
                searchq |= qob

        if idlist:
            # idlist contains int and str entries
            try:
                ids = map(lambda x: int(x), idlist)
            except ValueError:
                # deny any access in case of an incorrect id
                ids = []

            searchq &= (
                models.Q(
                    id__in=ids,
                    fake_id__isnull=True
                ) | models.Q(fake_id__in=ids)
            )

        # list only unlisted if explicity requested or export or:
        # if it has high priority (only for special users)
        # listing prioritized, unlisted content is different to the broader
        # search
        if self.request.is_special_user:
            # all other scopes than list can show here _unlisted
            # this includes export
            if  self.scope == "list" and "_unlisted" not in searchlist:
                searchq_exc |= models.Q(
                    info__contains="\nunlisted\n", priority__lte=0
                )
        else:
            searchq_exc |= models.Q(info__contains="\nunlisted\n")
        order = self.get_ordering(counter > 0)
        # distinct required?
        ret = ret.filter(searchq & ~searchq_exc).distinct()
        if order:
            ret = ret.order_by(*order)
        return ret


class ContentIndex(ReferrerMixin, ContentBase, ListView):
    model = AssignedContent
    scope = "list"
    no_nonce_usercomponent = False

    def dispatch_extra(self, request, *args, **kwargs):
        # only owner can use referring feature
        if "referrer" in self.request.GET and self.request.is_owner:
            self.object_list = self.get_queryset()
            return self.handle_referrer()
        return None

    def get_queryset(self):
        return super().get_queryset().filter(
            usercomponent=self.usercomponent
        )

    def get_usercomponent(self):
        query = {"id": self.kwargs["id"]}
        query["nonce"] = self.kwargs["nonce"]
        return get_object_or_404(
            UserComponent.objects.select_related(
                "user", "user__spider_info",
            ).prefetch_related("protections"),
            **query
        )

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        if self.request.is_owner:
            context["content_variants"] = \
                self.request.user.spider_info.allowed_content.exclude(
                    ctype__contains=VariantType.feature.value
                )
            context["content_variants_used"] = \
                self.request.user.spider_info.allowed_content.filter(
                    assignedcontent__usercomponent=self.usercomponent
                ).exclude(
                    ctype__contains=VariantType.feature.value
                )
        context["is_public_view"] = self.usercomponent.public
        context["has_unlisted"] = self.usercomponent.contents.filter(
            info__contains="\nunlisted\n"
        ).exists()

        context["remotelink"] = context["spider_GET"].copy()
        context["auth_token"] = None
        if self.request.auth_token:
            context["auth_token"] = self.request.auth_token.token
        context["remotelink"] = "{}{}?{}".format(
            context["hostpart"],
            reverse("spider_base:ucontent-list", kwargs={
                "id": self.usercomponent.id,
                "nonce": self.usercomponent.nonce
            }),
            context["remotelink"].urlencode()
        )
        return context

    def test_func(self):
        staff_perm = not self.usercomponent.is_index
        if staff_perm:
            staff_perm = "spider_base.view_usercomponent"
        # user token is tested later
        if self.has_special_access(
            user_by_login=True, user_by_token=False,
            staff=staff_perm, superuser=True
        ):
            self.request.auth_token = self.create_admin_token()
            return True
        # block view on special objects for non user and non superusers
        if self.usercomponent.is_index:
            return False
        # export is only available for user and superuser
        if self.scope == "export":
            # if self.request.user.is_staff:
            #     return True
            return False

        return self.test_token()

    def get_paginate_by(self, queryset):
        if self.scope == "export" or "raw" in self.request.GET:
            return None
        return getattr(settings, "CONTENTS_PER_PAGE", 25)

    def render_to_response(self, context):
        if context["scope"] != "export" and "raw" not in self.request.GET:
            return super().render_to_response(context)

        session_dict = {
            "request": self.request,
            "context": context,
            "scope": context["scope"],
            "uc": self.usercomponent,
            "hostpart": context["hostpart"],
            "sourceref": URIRef(context["hostpart"] + self.request.path)
        }
        g = Graph()
        g.namespace_manager.bind("spkc", spkcgraph, replace=True)

        embed = False
        if (
            context["scope"] == "export" or
            self.request.GET.get("raw", "") == "embed"
        ):
            embed = True

        p = paginate_stream(
            context["object_list"],
            getattr(settings, "SERIALIZED_PER_PAGE", 50),
            getattr(settings, "SERIALIZED_MAX_DEPTH", 5)
        )
        page = 1
        try:
            page = int(self.request.GET.get("page", "1"))
        except Exception:
            pass

        if hasattr(self.request, "token_expires"):
            session_dict["expires"] = self.request.token_expires.strftime(
                "%a, %d %b %Y %H:%M:%S %z"
            )
            if page <= 1:
                add_property(
                    g, "token_expires", ob=session_dict["request"],
                    ref=session_dict["sourceref"]
                )
        if page <= 1:
            g.add((
                session_dict["sourceref"],
                spkcgraph["scope"],
                Literal(context["scope"])
            ))
            g.add((
                session_dict["sourceref"],
                spkcgraph["strength"],
                Literal(self.usercomponent.strength)
            ))
            if context["referrer"]:
                g.add((
                    session_dict["sourceref"],
                    spkcgraph["referrer"],
                    Literal(context["referrer"], datatype=XSD.anyURI)
                ))
            if context["token_strength"]:
                add_property(
                    g, "token_strength", ref=session_dict["sourceref"],
                    literal=context["token_strength"]
                )
            for intention in context["intentions"]:
                add_property(
                    g, "intentions", ref=session_dict["sourceref"],
                    literal=intention, datatype=XSD.string
                )

        serialize_stream(
            g, p, session_dict,
            page=page,
            embed=embed
        )

        ret = HttpResponse(
            g.serialize(format="turtle"),
            content_type="text/turtle;charset=utf-8"
        )

        if session_dict.get("expires", None):
            ret['X-Token-Expires'] = session_dict["expires"]
        return ret


class ContentAdd(ContentBase, CreateView):
    scope = "add"
    model = ContentVariant
    also_authenticated_users = True

    def get(self, request, *args, **kwargs):
        self.object = self.get_object()
        return self.render_to_response(self.get_context_data())

    def post(self, request, *args, **kwargs):
        self.object = self.get_object()
        return self.render_to_response(self.get_context_data())

    def get_queryset(self):
        # use requesting user as base if he can add this type of content
        return self.request.user.spider_info.allowed_content.exclude(
            ctype__contains=VariantType.feature.value
        )

    def test_func(self):
        # test if user and check if user is allowed to create content
        if self.has_special_access(
            user_by_login=True, user_by_token=True, superuser=False
        ):
            return True
        return False

    def get_context_data(self, **kwargs):
        kwargs["user_content"] = AssignedContent(
            usercomponent=self.usercomponent,
            ctype=self.object
        )
        kwargs["content_type"] = self.object.installed_class
        form_kwargs = {
            "instance": kwargs["user_content"],
            "initial": {
                "usercomponent": self.usercomponent
            }
        }
        if self.request.method in ('POST', 'PUT'):
            form_kwargs.update({
                'data': self.request.POST,
                # 'files': self.request.FILES,
            })
        kwargs["form"] = UserContentForm(**form_kwargs)
        return super().get_context_data(**kwargs)

    def get_form(self):
        # should never be called
        raise NotImplementedError

    def get_object(self, queryset=None):
        if not queryset:
            queryset = self.get_queryset()
        qquery = models.Q(
            name=self.kwargs["type"],
            strength__lte=self.usercomponent.strength
        )
        return get_object_or_404(queryset, qquery)

    def render_to_response(self, context):
        ucontent = context.pop("user_content")
        ob = context["content_type"].static_create(
            associated=ucontent, **context
        )
        rendered = ob.render(**ob.kwargs)

        # return response if content returned response
        if isinstance(rendered, HttpResponseBase):
            return rendered
        # show framed output
        context["content"] = rendered
        # redirect if saving worked
        if getattr(ob, "id", None):
            assert(hasattr(ucontent, "id") and ucontent.usercomponent)
            return redirect(
                'spider_base:ucontent-access', id=ucontent.id,
                nonce=ucontent.nonce, access="update"
            )
        return super().render_to_response(context)


class ContentAccess(ReferrerMixin, ContentBase, UpdateView):
    scope = "access"
    form_class = UserContentForm
    model = AssignedContent

    def dispatch_extra(self, request, *args, **kwargs):
        # done in get_queryset
        # if getattr(self.request, "auth_token", None):
        #     ids = self.request.auth_token.extra.get("ids", None)
        #     if ids is not None and self.object.id not in ids:
        #         return self.handle_no_permission()
        if "referrer" in self.request.GET and self.request.is_owner:
            self.object_list = self.model.objects.filter(
                pk=self.object.pk
            )
            return self.handle_referrer()

        return None

    def dispatch(self, request, *args, **kwargs):
        _scope = kwargs["access"]
        # special scopes which should be not available as url parameter
        # raw is also deceptive because view and raw=? = raw scope
        if _scope in ["add", "list", "raw"]:
            raise PermissionDenied("Deceptive scopes")
        self.scope = _scope
        return super().dispatch(request, *args, **kwargs)

    def get(self, request, *args, **kwargs):
        self.object = self.get_object()
        context = {"form": None}
        if self.scope == "update":
            context["form"] = self.get_form()
        return self.render_to_response(self.get_context_data(**context))

    def post(self, request, *args, **kwargs):
        self.object = self.get_object()
        context = {"form": None}
        # other than update have no form
        if self.scope == "update":
            context["form"] = self.get_form()
            if context["form"].is_valid():
                self.object = context["form"].save()
                # nonce changed => path has changed
                if self.object.nonce != self.kwargs["nonce"]:
                    return redirect(
                        'spider_base:ucontent-access',
                        id=self.object.id,
                        nonce=self.object.nonce, access="update"
                    )
                context["form"] = self.get_form_class()(
                    **self.get_form_success_kwargs()
                )
        return self.render_to_response(self.get_context_data(**context))

    def get_context_data(self, **kwargs):
        kwargs["is_public_view"] = (
            self.usercomponent.public and
            self.scope not in ("add", "update", "update_raw")
        )
        context = super().get_context_data(**kwargs)

        if self.scope != "add":
            context["remotelink"] = context["spider_GET"].copy()
            context["auth_token"] = None
            if self.request.auth_token:
                context["auth_token"] = self.request.auth_token.token
            context["remotelink"] = "{}{}?{}".format(
                context["hostpart"],
                reverse("spider_base:ucontent-access", kwargs={
                    "id": self.object.id,
                    "nonce": self.object.nonce,
                    "access": "view"
                }),
                context["remotelink"].urlencode()
            )
        return context

    def get_form_success_kwargs(self):
        """Return the keyword arguments for instantiating the form."""
        return {
            'initial': self.get_initial(),
            'instance': self.object,
            'prefix': self.get_prefix()
        }

    def test_func(self):
        # give user and staff the ability to update Content
        # except it is index, in this case only the user can update
        # reason: admins could be tricked into malicious updates
        # for index the same reason as for add
        uncritically = self.usercomponent.name != "index"
        staff_perm = uncritically
        if staff_perm:
            staff_perm = "spider_base.view_assignedcontent"
            if self.scope in ["update", "raw_update"]:
                staff_perm = "spider_base.update_assignedcontent"
        # user token is tested later
        if self.has_special_access(
            staff=staff_perm, superuser=uncritically,
            user_by_token=False, user_by_login=True
        ):
            self.request.auth_token = self.create_admin_token()
            return True
        minstrength = 0
        if self.scope not in ["update", "raw_update", "export"]:
            minstrength = 4
        return self.test_token(minstrength)

    def render_to_response(self, context):
        rendered = self.object.content.render(
            **context
        )
        # return response if content returned response
        # useful for redirects and raw update
        if isinstance(rendered, HttpResponseBase):
            return rendered

        context["content"] = rendered
        return super().render_to_response(context)

    def get_usercomponent(self):
        q = models.Q(
            contents__id=self.kwargs["id"],
            contents__fake_id__isnull=True
        ) | models.Q(contents__fake_id=self.kwargs["id"])
        q &= models.Q(contents__nonce=self.kwargs["nonce"])
        return get_object_or_404(
            UserComponent.objects.prefetch_related("protections"),
            q
        )

    def get_user(self):
        return self.usercomponent.user

    def get_object(self, queryset=None):
        # can bypass idlist and searchlist with own queryset arg
        if not queryset:
            queryset = self.get_queryset()

        q = models.Q(
            id=self.kwargs["id"],
            fake_id__isnull=True
        ) | models.Q(fake_id=self.kwargs["id"])
        q &= models.Q(nonce=self.kwargs["nonce"])
        return get_object_or_404(
            queryset.select_related(
                "usercomponent", "usercomponent__user",
                "usercomponent__user__spider_info"
            ).filter(q)
        )


class ContentRemove(EntityDeletionMixin, DeleteView):
    model = AssignedContent
    usercomponent = None
    no_nonce_usercomponent = True

    def dispatch(self, request, *args, **kwargs):
        self.usercomponent = self.get_usercomponent()
        self.object = self.get_object()
        return super().dispatch(request, *args, **kwargs)

    def get_context_data(self, **kwargs):
        kwargs["uc"] = self.usercomponent
        return super().get_context_data(**kwargs)

    def get_success_url(self):
        return reverse(
            "spider_base:ucontent-list", kwargs={
                "id": self.usercomponent.id,
                "nonce":  self.usercomponent.nonce
            }
        )

    def get_object(self, queryset=None):
        if not queryset:
            queryset = self.get_queryset()
        return get_object_or_404(
            queryset, usercomponent=self.usercomponent,
            id=self.kwargs["id"], nonce=self.kwargs["nonce"]
        )
