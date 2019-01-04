__all__ = (
    "UserTestMixin", "UCTestMixin", "EntityDeletionMixin", "ReferrerMixin"
)

import logging
import hashlib
from urllib.parse import quote_plus

from datetime import timedelta


from django.contrib.auth.mixins import AccessMixin
from django.shortcuts import get_object_or_404
from django.contrib.auth import get_user_model, REDIRECT_FIELD_NAME
from django.http import (
    HttpResponseRedirect, HttpResponseServerError, HttpResponse
)
from django.utils import timezone
from django.conf import settings
from django.urls import reverse_lazy
from django.utils.translation import gettext


import requests
import certifi

from ..helpers import merge_get_url, get_settings_func
from ..constants import VariantType, index_names
from ..models import (
    UserComponent, AuthToken, TokenCreationError
)


class UserTestMixin(AccessMixin):
    no_nonce_usercomponent = False
    also_authenticated_users = False
    preserved_GET_parameters = set(["token", "protection"])
    login_url = reverse_lazy(getattr(
        settings,
        "LOGIN_URL",
        "auth:login"
    ))

    def dispatch_extra(self, request, *args, **kwargs):
        return None

    def dispatch(self, request, *args, **kwargs):
        _ = gettext
        self.request.is_elevated_request = False
        self.request.is_owner = False
        self.request.is_special_user = False
        self.request.auth_token = None
        try:
            user_test_result = self.test_func()
        except TokenCreationError as e:
            logging.exception(e)
            return HttpResponseServerError(
                _("Token creation failed, try again")
            )
        if not user_test_result:
            return self.handle_no_permission()
        if isinstance(user_test_result, str):
            return HttpResponseRedirect(redirect_to=user_test_result)
        ret = self.dispatch_extra(request, *args, **kwargs)
        if ret:
            return ret
        return super().dispatch(request, *args, **kwargs)

    def sanitize_GET(self):
        GET = self.request.GET.copy()
        for key in list(GET.keys()):
            if key not in self.preserved_GET_parameters:
                GET.pop(key, None)
        return GET

    def get_context_data(self, **kwargs):
        kwargs["raw_update_type"] = VariantType.raw_update.value
        kwargs["hostpart"] = "{}://{}".format(
            self.request.scheme, self.request.get_host()
        )
        kwargs["spider_GET"] = self.sanitize_GET()
        return super().get_context_data(**kwargs)

    # by default only owner can access view
    def test_func(self):
        if self.has_special_access(staff=False, superuser=False):
            return True
        return False

    def replace_token(self):
        GET = self.request.GET.copy()
        GET["token"] = self.request.auth_token.token
        return "?".join((self.request.path, GET.urlencode()))

    def create_token(self, special_user=None, extra=None):
        session_key = None
        if "token" not in self.request.GET:
            session_key = self.request.session.session_key
        token = AuthToken(
            usercomponent=self.usercomponent,
            session_key=session_key,
            created_by_special_user=special_user
        )
        if extra:
            token.extra = extra
        token.save()
        return token

    def create_admin_token(self):
        expire = timezone.now()-self.usercomponent.token_duration
        # delete old token, so no confusion happen
        self.usercomponent.authtokens.filter(
            created__lt=expire
        ).delete()
        # delete tokens from old sessions
        self.usercomponent.authtokens.exclude(
            session_key=self.request.session.session_key,
        ).filter(created_by_special_user=self.request.user).delete()

        # use session_key, causes deletion on logout
        token = self.usercomponent.authtokens.filter(
            session_key=self.request.session.session_key
        ).first()
        if token:
            return token
        return self.create_token(self.request.user)

    def remove_old_tokens(self, expire=None):
        if not expire:
            expire = timezone.now()-self.usercomponent.token_duration
        return self.usercomponent.authtokens.filter(
            created__lt=expire
        ).delete()

    def test_token(self):
        expire = timezone.now()-self.usercomponent.token_duration
        no_token = (self.usercomponent.required_passes == 0)

        # token not required
        if not no_token:
            # delete old token, so no confusion happen
            self.remove_old_tokens(expire)

            # generate key if not existent
            if not self.request.session.session_key:
                self.request.session.cycle_key()

            # only valid tokens here
            tokenstring = self.request.GET.get("token", None)
            if tokenstring or not self.request.session.session_key:
                # find by tokenstring
                token = self.usercomponent.authtokens.filter(
                    token=tokenstring
                ).first()
            else:
                # use session_key
                token = self.usercomponent.authtokens.filter(
                    session_key=self.request.session.session_key
                ).first()
            if token:
                self.request.token_expires = \
                    token.created+self.usercomponent.token_duration
                self.request.auth_token = token
                if not token.session_key and "token" not in self.request.GET:
                    return self.replace_token()
                if (
                    self.usercomponent.strength >=
                    settings.MIN_STRENGTH_EVELATION
                ) and not token.extra.get("weak", False):
                    self.request.is_elevated_request = True
                return True

        protection_codes = None
        if "protection" in self.request.GET:
            protection_codes = self.request.GET.getlist("protection")
        # execute protections for side effects even no_token
        self.request.protections = self.usercomponent.auth(
            request=self.request, scope=self.scope,
            protection_codes=protection_codes
        )
        if self.request.protections is True:
            # token not required
            if no_token:
                #
                if self.usercomponent.strength < 5:
                    return True
                if not self.usercomponent.features.filter(
                    name="PermissiveTokens"
                ):
                    return True
                token = self.create_token(extra={"weak": True})
            else:
                # is_elevated_request requires token
                if (
                    self.usercomponent.strength >=
                    settings.MIN_STRENGTH_EVELATION
                ):
                    self.request.is_elevated_request = True

                token = self.create_token(extra={"weak": False})

            self.request.token_expires = \
                token.created+self.usercomponent.token_duration
            self.request.auth_token = token
            if "token" in self.request.GET:
                return self.replace_token()
            return True
        return False

    def has_special_access(
        self, user=True, staff=False, superuser=True, staff_perm=None
    ):
        if not hasattr(self, "usercomponent"):
            self.usercomponent = self.get_usercomponent()
        if self.request.user == self.usercomponent.user:
            self.request.is_elevated_request = True
            self.request.is_owner = True
            self.request.is_special_user = True
            return True
        # remove user special state if is_fake
        if self.request.session.get("is_fake", False):
            return False
        if superuser and self.request.user.is_superuser:
            self.request.is_elevated_request = True
            self.request.is_special_user = True
            return True
        if staff and self.request.user.is_staff:
            if not staff_perm or self.request.user.has_perm(staff_perm):
                self.request.is_elevated_request = True
                self.request.is_special_user = True
                return True
        return False

    def get_user(self):
        """ Get user from user field or request """
        if (
                self.also_authenticated_users and
                "user" not in self.kwargs and
                self.request.user.is_authenticated
           ):
            return self.request.user

        model = get_user_model()
        margs = {model.USERNAME_FIELD: None}
        margs[model.USERNAME_FIELD] = self.kwargs.get("user", None)
        return get_object_or_404(
            model.objects.select_related("spider_info"),
            **margs
        )

    def get_usercomponent(self):
        ucname = self.kwargs["name"]
        if ucname in index_names:
            if self.request.session["is_fake"]:
                ucname = "fake_index"
            else:
                ucname = "index"
        query = {
            "name": ucname,
            "user": self.get_user()
        }
        if not self.no_nonce_usercomponent:
            query["nonce"] = self.kwargs["nonce"]
        return get_object_or_404(
            UserComponent.objects.prefetch_related(
                "authtokens", "protections"
            ),
            **query
        )

    def handle_no_permission(self):
        # in case no protections are used (e.g. add content)
        p = getattr(self.request, "protections", False)
        if not bool(p):
            return super().handle_no_permission()
        # should be never true here
        assert(p is not True)
        context = {
            "spider_GET": self.sanitize_GET(),
            "LOGIN_URL": self.get_login_url(),
            "scope": getattr(self, "scope", None),
            "uc": self.usercomponent,
            "index_names": index_names,
            "object": getattr(self, "object", None),
            "is_public_view": self.usercomponent.public
        }
        return self.response_class(
            request=self.request,
            template=self.get_noperm_template_names(),
            # render with own context; get_context_data may breaks stuff or
            # disclose informations
            context=context,
            using=self.template_engine,
            content_type=self.content_type
        )

    def get_noperm_template_names(self):
        return "spider_protections/protections.html"


class UCTestMixin(UserTestMixin):
    usercomponent = None

    def dispatch(self, request, *args, **kwargs):
        self.usercomponent = self.get_usercomponent()
        return super(UCTestMixin, self).dispatch(request, *args, **kwargs)

    def post(self, request, *args, **kwargs):
        # for protections
        return self.get(request, *args, **kwargs)

    def put(self, request, *args, **kwargs):
        # for protections
        return self.get(request, *args, **kwargs)


class ReferrerMixin(object):
    _ = gettext

    def refer_with_post(self, context, token):
        _ = gettext
        # application/x-www-form-urlencoded is best here,
        # for beeing compatible to most webservers
        # client side rdf is no problem
        # NOTE: csrf must be disabled or use csrf token from GET,
        #       here is no way to know the token value
        try:
            ret = requests.post(
                context["referrer"],
                data={
                    "token": token.token,
                    "hash_algorithm": settings.SPIDER_HASH_ALGORITHM,
                },
                headers={
                    "Referer": merge_get_url("%s%s" % (
                        context["hostpart"],
                        self.request.get_full_path()
                    ), token=None, referrer=None, raw=None)
                },
                verify=certifi.where()
            )
        except requests.exceptions.SSLError:
            return HttpResponse(
                status=400,
                content=_('doesn\'t support ssl: %(url)s') % {
                    "url": context["referrer"]
                }
            )
        except Exception:
            return HttpResponse(
                status=400,
                content=_('failure: %(url)s') % {
                    "url": context["referrer"]
                }
            )
        if ret.status_code not in (200, 201):
            return HttpResponseRedirect(
                redirect_to=merge_get_url(
                    context["referrer"],
                    error="post_failed"
                )
            )
        h = hashlib.new(settings.SPIDER_HASH_ALGORITHM)
        h.update(token.token.encode("ascii", "ignore"))
        return HttpResponseRedirect(
            redirect_to=merge_get_url(
                context["referrer"],
                hash=h.hexdigest()
            )
        )

    def refer_with_get(self, context, token):
        return HttpResponseRedirect(
            redirect_to=merge_get_url(
                context["referrer"],
                token=token.token
            )
        )

    def handle_referrer(self):
        _ = gettext
        if (
            self.request.user != self.usercomponent.user and
            not self.request.auth_token
        ):
            return HttpResponseRedirect(
                redirect_to="{}?{}={}".format(
                    self.get_login_url(),
                    REDIRECT_FIELD_NAME,
                    quote_plus(self.request.get_full_path())
                )
            )

        context = self.get_context_data()
        context["referrer"] = merge_get_url(self.request.GET["referrer"])
        if not get_settings_func(
            "SPIDER_URL_VALIDATOR",
            "spkcspider.apps.spider.functions.validate_url_default"
        )(context["referrer"]):
            return HttpResponse(
                status=400,
                content=_('Insecure url: %(url)s') % {
                    "url": context["referrer"]
                }
            )
        context["object_list"] = self.object_list

        action = self.request.POST.get("action", None)
        if action == "confirm":
            # create only new token when admin token
            if self.usercomponent.user == self.request.user:
                authtoken = AuthToken(
                    usercomponent=self.usercomponent,
                    extra={
                        "ids": list(
                            self.object_list.values_list("id", flat=True)
                        ),
                        "referrer": context["referrer"],
                        "weak": False
                    }
                )
                try:
                    authtoken.save()
                except TokenCreationError as e:
                    logging.exception(e)
                    return HttpResponseServerError(
                        _("Token creation failed, try again")
                    )
                token = authtoken
            else:
                # recycle token
                # NOTE: one token, one referrer
                token = self.request.auth_token.token
                token.extra["referrer"] = context["referrer"]
                token.save()
                token = token
            if self.request.GET.get("sl", "") == "true":
                return self.refer_with_get(context, token)
            return self.refer_with_post(context, token)

        elif action == "cancel":
            return HttpResponseRedirect(
                redirect_to=merge_get_url(
                    context["referrer"],
                    error="canceled"
                )
            )
        else:
            return self.response_class(
                request=self.request,
                template=self.get_referrer_template_names(),
                context=context,
                using=self.template_engine,
                content_type=self.content_type
            )

    def get_referrer_template_names(self):
        return "spider_protections/referring.html"


class EntityDeletionMixin(UserTestMixin):
    object = None
    http_method_names = ['get', 'post', 'delete']

    def get_context_data(self, **kwargs):
        _time = self.get_required_timedelta()
        if _time and self.object.deletion_requested:
            now = timezone.now()
            if self.object.deletion_requested + _time >= now:
                kwargs["remaining"] = timedelta(seconds=0)
            else:
                kwargs["remaining"] = self.object.deletion_requested+_time-now
        return super().get_context_data(**kwargs)

    def get_required_timedelta(self):
        _time = self.object.content.deletion_period
        if _time:
            _time = timedelta(seconds=_time)
        else:
            _time = timedelta(seconds=0)
        return _time

    def delete(self, request, *args, **kwargs):
        # hack for compatibility to ContentRemove
        if getattr(self.object, "name", "") in index_names:
            return self.handle_no_permission()
        _time = self.get_required_timedelta()
        if _time:
            now = timezone.now()
            if self.object.deletion_requested:
                if self.object.deletion_requested+_time >= now:
                    return self.get(request, *args, **kwargs)
            else:
                self.object.deletion_requested = now
                self.object.save()
                return self.get(request, *args, **kwargs)
        self.object.delete()
        return HttpResponseRedirect(self.get_success_url())

    def post(self, request, *args, **kwargs):
        # because forms are screwed (delete not possible)
        if request.POST.get("action") == "reset":
            return self.reset(request, *args, **kwargs)
        elif request.POST.get("action") == "delete":
            return self.delete(request, *args, **kwargs)
        return super().get(request, *args, **kwargs)

    def reset(self, request, *args, **kwargs):
        self.object.deletion_requested = None
        self.object.save(update_fields=["deletion_requested"])
        return HttpResponseRedirect(self.get_success_url())
