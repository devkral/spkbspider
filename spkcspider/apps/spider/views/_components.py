
__all__ = (
    "ComponentIndex", "ComponentPublicIndex", "ComponentCreate",
    "ComponentUpdate", "ComponentDelete", "TokenDelete"
)

from django.views.generic.list import ListView
from django.views.generic.edit import CreateView, UpdateView, DeleteView
from django.shortcuts import get_object_or_404, redirect
from django.db import models
from django.http import HttpResponse, JsonResponse
from django.conf import settings
from django.urls import reverse

from rdflib import Graph, Literal, URIRef

from ._core import UserTestMixin, UCTestMixin, EntityDeletionMixin
from ..constants.static import index_names
from ..forms import UserComponentForm
from ..contents import installed_contents
from ..models import (
    UserComponent, TravelProtection, AuthToken
)
from ..constants import spkcgraph
from ..serializing import paginate_stream, serialize_stream


class ComponentIndexBase(ListView):
    scope = "list"

    def get_context_data(self, **kwargs):
        kwargs["scope"] = self.scope
        return super().get_context_data(**kwargs)

    def get_queryset(self):
        searchq = models.Q()
        searchq_exc = models.Q()
        infoq = models.Q()
        infoq_exc = models.Q()
        order = None
        counter = 0
        max_counter = 30  # against ddos
        if "search" in self.request.POST or "info" in self.request.POST:
            searchlist = self.request.POST.getlist("search")
            infolist = self.request.POST.getlist("info")
            idlist = self.request.POST.getlist("id")
        else:
            searchlist = self.request.GET.getlist("search")
            infolist = self.request.GET.getlist("info")
            idlist = self.request.POST.getlist("id")

        for item in searchlist:
            if counter > max_counter:
                break
            counter += 1
            if len(item) == 0:
                continue
            if item.startswith("!!"):
                _item = item[1:]
            elif item.startswith("!"):
                _item = item[1:]
            else:
                _item = item
            qob = models.Q(
                contents__info__icontains=_item
            )
            qob |= models.Q(
                description__icontains=_item
            )
            if _item == "index":
                qob |= models.Q(
                    strength=10
                )
            else:
                qob |= models.Q(
                    name__icontains=_item,
                    strength__lt=10
                )
            if item.startswith("!!"):
                searchq |= qob
            elif item.startswith("!"):
                searchq_exc |= qob
            else:
                searchq |= qob

        for item in infolist:
            if counter > max_counter:
                break
            counter += 1
            if len(item) == 0:
                continue
            if item.startswith("!!"):
                infoq |= models.Q(contents__info__contains="\n%s\n" % item[1:])
            elif item.startswith("!"):
                infoq_exc |= models.Q(
                    contents__info__contains="\n%s\n" % item[1:]
                )
            else:
                infoq |= models.Q(contents__info__contains="\n%s\n" % item)
        if self.request.GET.get("protection", "") == "false":
            searchq &= models.Q(required_passes=0)

        if idlist:
            ids = map(lambda x: int(x), idlist)
            searchq &= (
                models.Q(
                    contents__id__in=ids,
                    contents__fake_id__isnull=True
                ) |
                models.Q(contents__fake_id__in=ids)
            )

        if self.scope != "export" and "raw" not in self.request.GET:
            order = self.get_ordering(counter > 0)
        ret = self.model.objects.prefetch_related(
            "contents"
        ).filter(
            searchq & ~searchq_exc & infoq & ~infoq_exc,
        ).distinct()
        if order:
            ret = ret.order_by(*order)
        return ret

    def get_paginate_by(self, queryset):
        if self.scope == "export" or "raw" in self.request.GET:
            return None
        return getattr(settings, "COMPONENTS_PER_PAGE", 25)

    def render_to_response(self, context):
        if self.scope != "export" and "raw" not in self.request.GET:
            return super().render_to_response(context)
        session_dict = {
            "request": self.request,
            "context": context,
            "scope": self.scope,
            "expires": None,
            "hostpart": context["hostpart"],
            "uc_namespace": spkcgraph["components"],
            "sourceref": URIRef(context["hostpart"] + self.request.path)
        }

        g = Graph()
        g.namespace_manager.bind("spkc", spkcgraph, replace=True)
        p = paginate_stream(
            context["object_list"],
            getattr(settings, "SERIALIZED_PER_PAGE", 50),
            getattr(settings, "SERIALIZED_MAX_DEPTH", 5),
            contentnize=(
                self.scope == "export" or
                self.request.GET.get("raw", "") == "embed"
            )
        )
        page = 1
        try:
            page = int(self.request.GET.get("page", "1"))
        except Exception:
            pass
        if page <= 1:
            g.add((
                session_dict["sourceref"],
                spkcgraph["scope"],
                Literal(context["scope"])
            ))
            g.add((
                session_dict["sourceref"], spkcgraph["strength"],
                Literal(self.source_strength)
            ))

        serialize_stream(
            g, p, session_dict,
            page=page,
            embed=(
                self.scope == "export" or
                self.request.GET.get("raw", "") == "embed"
            )
        )

        ret = HttpResponse(
            g.serialize(format="turtle"),
            content_type="text/turtle;charset=utf-8"
        )
        return ret


class ComponentPublicIndex(ComponentIndexBase):
    model = UserComponent
    is_home = False
    source_strength = 0
    allowed_GET_parameters = set(["protection", "raw"])

    def dispatch(self, request, *args, **kwargs):
        self.request.is_elevated_request = False
        self.request.is_owner = False
        self.request.auth_token = None
        return super().dispatch(request, *args, **kwargs)

    def post(self, request, *args, **kwargs):
        return self.get(request, *args, **kwargs)

    def get_context_data(self, **kwargs):
        kwargs["is_public_view"] = True
        kwargs["hostpart"] = "{}://{}".format(
            self.request.scheme, self.request.get_host()
        )

        GET = self.request.GET.copy()
        # parameters preserved in search
        for key in list(GET.keys()):
            if key not in self.allowed_GET_parameters:
                GET.pop(key, None)
        kwargs["spider_GET"] = GET
        return super().get_context_data(**kwargs)

    def get_queryset(self):
        query = super().get_queryset()
        q = models.Q(public=True, strength__lt=5)
        if self.is_home:
            q &= models.Q(featured=True)
        return query.filter(q)

    def get_ordering(self, issearching=False):
        if not issearching:
            return ("strength", "-modified",)
        else:
            return ("name", "user__username")


class ComponentIndex(UCTestMixin, ComponentIndexBase):
    model = UserComponent
    source_strength = 10
    also_authenticated_users = True
    no_nonce_usercomponent = True

    user = None

    def dispatch(self, request, *args, **kwargs):
        self.user = self.get_user()
        return super().dispatch(request, *args, **kwargs)

    def post(self, request, *args, **kwargs):
        return self.get(request, *args, **kwargs)

    def get_ordering(self, issearching=False):
        if issearching:
            # MUST use strength here, elsewise travel mode can be exposed
            return ("-strength", "name",)
        return ("-modified",)

    def get_context_data(self, **kwargs):
        kwargs["component_user"] = self.user
        kwargs["username"] = getattr(self.user, self.user.USERNAME_FIELD)
        kwargs["scope"] = self.scope
        kwargs["is_public_view"] = False
        return super().get_context_data(**kwargs)

    def test_func(self):
        if self.has_special_access(staff=True):
            return True
        return False

    def get_queryset(self):
        query = super().get_queryset()
        q = models.Q()
        # doesn't matter if it is same user, lazy
        travel = TravelProtection.objects.get_active()
        # remove all travel protected components if not admin
        if self.request.user == self.user:
            q &= ~models.Q(
                travel_protected__in=travel
            )
        if self.request.session.get("is_fake", False):
            q &= ~models.Q(name="index")
        else:
            q &= ~models.Q(name="fake_index")
        return query.filter(q)

    def get_usercomponent(self):
        ucname = "index"
        if self.request.session.get("is_fake", False):
            ucname = "fake_index"
        return get_object_or_404(
            UserComponent, user=self.user, name=ucname
        )


class ComponentCreate(UserTestMixin, CreateView):
    model = UserComponent
    form_class = UserComponentForm
    also_authenticated_users = True
    no_nonce_usercomponent = True

    def get_success_url(self):
        return reverse(
            "spider_base:ucomponent-update", kwargs={
                "name": self.object.name,
                "nonce": self.object.nonce
            }
        )

    def get_usercomponent(self):
        query = {}
        if self.request.session.get("is_fake", False):
            query["name"] = "fake_index"
        else:
            query["name"] = "index"
        query["user"] = self.get_user()
        return get_object_or_404(UserComponent, **query)

    def get_context_data(self, **kwargs):
        kwargs["available"] = installed_contents.keys()
        return super().get_context_data(**kwargs)

    def get_form_kwargs(self):
        ret = super().get_form_kwargs()
        ret["instance"] = self.model(user=self.get_user())
        ret['request'] = self.request
        return ret


class ComponentUpdate(UserTestMixin, UpdateView):
    model = UserComponent
    form_class = UserComponentForm
    also_authenticated_users = True

    def get_context_data(self, **kwargs):
        # for create_admin_token
        self.usercomponent = self.object
        self.request.auth_token = self.create_admin_token()
        context = super().get_context_data(**kwargs)
        context["content_variants"] = \
            self.usercomponent.user_info.allowed_content.all()
        context["content_variants_used"] = \
            self.usercomponent.user_info.allowed_content.filter(
                assignedcontent__usercomponent=self.usercomponent
            )
        context["remotelink"] = context["spider_GET"].copy()
        context["remotelink"] = "{}{}?{}".format(
            context["hostpart"],
            reverse("spider_base:ucontent-list", kwargs={
                "id": self.usercomponent.id,
                "nonce": self.usercomponent.nonce
            }),
            context["remotelink"].urlencode()
        )
        # this is always available
        context["auth_token"] = self.request.auth_token.token
        return context

    def get_object(self, queryset=None):
        if not queryset:
            queryset = self.get_queryset()
        return get_object_or_404(
            queryset.prefetch_related(
                "protections",
            ),
            user=self.get_user(), name=self.kwargs["name"],
            nonce=self.kwargs["nonce"]
        )

    def get_form_kwargs(self):
        ret = super().get_form_kwargs()
        ret['request'] = self.request
        return ret

    def get_form_success_kwargs(self):
        """Return the keyword arguments for instantiating the form."""
        return {
            'initial': self.get_initial(),
            'prefix': self.get_prefix(),
            'instance': self.object,
            'request': self.request
        }

    def form_valid(self, form):
        self.object = form.save()
        if (
            self.kwargs["nonce"] != self.object.nonce or
            self.kwargs["name"] != self.object.name
        ):
            return redirect(
                "spider_base:ucomponent-update",
                name=self.object.name,
                nonce=self.object.nonce
            )
        return self.render_to_response(
            self.get_context_data(
                form=self.get_form_class()(**self.get_form_success_kwargs())
            )
        )


class TokenDelete(UCTestMixin, DeleteView):
    no_nonce_usercomponent = True
    also_authenticated_users = True

    def get_object(self):
        return None

    def delete(self, request, *args, **kwargs):
        self.remove_old_tokens()
        query = AuthToken.objects.filter(
            usercomponent=self.usercomponent,
            token__in=self.request.POST.getlist("token")
        )
        if query.filter(
            created_by_special_user=self.request.user
        ).exists():
            self.request.auth_token = self.create_token(self.request.user)
        query.delete()
        del query
        return self.get(request, *args, **kwargs)

    def post(self, request, *args, **kwargs):
        return self.delete(self, request, *args, **kwargs)

    def get(self, request, *args, **kwargs):
        self.remove_old_tokens()
        response = {
            "tokens": [
                {
                    "expires": (
                        i.created +
                        self.usercomponent.token_duration
                    ).strftime("%a, %d %b %Y %H:%M:%S %z"),
                    "token": i.token


                } for i in AuthToken.objects.filter(
                    usercomponent=self.usercomponent
                )
            ],
            "admin": AuthToken.objects.filter(
                usercomponent=self.usercomponent,
                created_by_special_user=self.request.user
            ).first()
        }
        if response["admin"]:
            response["admin"] = response["admin"].token
        return JsonResponse(response)


class ComponentDelete(EntityDeletionMixin, DeleteView):
    model = UserComponent
    fields = []
    object = None

    def dispatch(self, request, *args, **kwargs):
        self.user = self.get_user()
        self.object = self.get_object()
        self.usercomponent = self.object
        return super().dispatch(request, *args, **kwargs)

    def get_success_url(self):
        username = getattr(self.user, self.user.USERNAME_FIELD)
        return reverse(
            "spider_base:ucomponent-list", kwargs={
                "user": username
            }
        )

    def get_context_data(self, **kwargs):
        kwargs["uc"] = self.usercomponent
        return super().get_context_data(**kwargs)

    def delete(self, request, *args, **kwargs):
        if self.object.name in index_names:
            return self.handle_no_permission()
        super().delete(request, *args, **kwargs)

    def get_object(self, queryset=None):
        if not queryset:
            queryset = self.get_queryset()
        return get_object_or_404(
            queryset, user=self.user, name=self.kwargs["name"],
            nonce=self.kwargs["nonce"]
        )
