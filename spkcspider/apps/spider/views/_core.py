__all__ = ("UserTestMixin", "UCTestMixin")

from django.contrib.auth.mixins import UserPassesTestMixin
from django.shortcuts import get_object_or_404
from django.contrib.auth import get_user_model
from django.http.response import HttpResponseBase

from ..constants import ProtectionType, UserContentType
from ..models import UserComponent


class UserTestMixin(UserPassesTestMixin):
    results_tests = None

    def get_context_data(self, **kwargs):
        kwargs["UserContentType"] = UserContentType
        kwargs["ProtectionType"] = ProtectionType
        return super().get_context_data(**kwargs)

    # by default only owner can access view
    def test_func(self):
        if self.has_special_access(staff=False, superuser=False):
            return True
        return False

    def has_special_access(self, staff=False, superuser=True):
        if self.request.user == self.get_user():
            return True
        if superuser and self.request.user.is_superuser:
            return True
        if staff and self.request.user.is_staff:
            return True
        return False

    def get_user(self):
        model = get_user_model()
        margs = {model.USERNAME_FIELD: None}
        if "user" in self.kwargs:
            margs[model.USERNAME_FIELD] = self.kwargs["user"]
        elif self.request.user.is_authenticated:
            return self.request.user
        return get_object_or_404(model, **margs)

    def get_usercomponent(self):
        query = {"name": self.kwargs["name"]}
        query["user"] = self.get_user()
        if query["user"] != self.request.user:
            query["nonce"] = self.kwargs["nonce"]
        return get_object_or_404(UserComponent, **query)

    def handle_no_permission(self):
        # in case no protections are used (e.g. add content)
        p = getattr(self.request, "protections", False)
        if not bool(p):
            return super().handle_no_permission()
        # should be never true here
        assert(p is not True)
        if len(p) == 1:
            if isinstance(p[0].result, HttpResponseBase):
                return p[0].result
        return self.response_class(
            request=self.request,
            template=self.get_noperm_template_names(),
            # render with own context; get_context_data may breaks stuff or
            # disclose informations
            context={},
            using=self.template_engine,
            content_type=self.content_type
        )

    def get_noperm_template_names(self):
        return "spider_protections/protections.html"


class UCTestMixin(UserTestMixin):
    usercomponent = None

    def dispatch(self, request, *args, **kwargs):
        self.usercomponent = self.get_usercomponent()
        # get_test_func executed later
        # if required: check, that function is called only once
        # user_test_result = self.get_test_func()()
        # if not user_test_result:
        #     return self.handle_no_permission()
        return super(UCTestMixin, self).dispatch(request, *args, **kwargs)

    def post(self, request, *args, **kwargs):
        # for protections
        return self.get(request, *args, **kwargs)

    def put(self, request, *args, **kwargs):
        # for protections
        return self.get(request, *args, **kwargs)
