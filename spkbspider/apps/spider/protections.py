"""
installed_protections, add_protection
namespace: spiderucs

"""

__all__ = ("add_protection", "ProtectionType", "check_blacklisted",
           "installed_protections", "BaseProtection", "ProtectionResult")

from collections import namedtuple
import enum

from django.conf import settings
from django import forms
from django.utils.translation import ugettext_lazy as _

installed_protections = {}


def check_blacklisted(name):
    if name in getattr(settings, "BLACKLISTED_PROTECTIONS", {}):
        return False
    return True


def add_protection(klass):
    if klass.name != "allow":
        if klass.name in getattr(settings, "BLACKLISTED_PROTECTIONS", {}):
            return klass
    if klass.name in installed_protections:
        raise Exception("Duplicate protection name")
    installed_protections[klass.name] = klass
    return klass


ProtectionResult = namedtuple("ProtectionResult", ["result", "protection"])


class ProtectionType(enum.Enum):
    # receives: request, scope
    access_control = "\x00"
    # receives: request, scope, password
    authentication = "\x01"
    # forget about recovery, every recovery method is authentication
    # and will be misused this way
    # The only real recovery is by staff and only if there is a secret


class BaseProtection(forms.Form):
    """
        Base for Protections
        Usage: use form to define some configurable fields for configuration
        use auth to validate: in this case:
            template_name, render, form variable are used
    """
    active = forms.BooleanField(required=True)

    # ptype= 0: access control, 1: authentication, 2: recovery
    # 1, 2 require render
    ptype = ProtectionType.access_control

    template_name = None
    form = None
    # optional render function
    # render = None

    # auto populated, instance
    protection = None
    assigned = None

    def __init__(self, *args, assigned=None, **kwargs):
        self.protection = kwargs.pop("protection")
        initial = None
        if assigned:
            initial = assigned.filter(protection=self.protection).first()
        if initial:
            initial = initial.protectiondata
        super().__init__(*args, initial=initial, **kwargs)

    @classmethod
    def auth(cls, **kwargs):
        return False


# if specified with multiple protections all protections must be fullfilled
@add_protection
class AllowProtection(BaseProtection):
    name = "allow"
    ptype = ProtectionType.access_control

    @classmethod
    def auth(cls, **_kwargs):
        return True

    def __str__(self):
        return _("Allow")


# def friend_query():
#    return get_user_model().objects.filter(active=True)

# only friends have access
# @add_protection
# class FriendProtection(BaseProtection):
#    name = "friends"
#    users = forms.ModelMultipleChoiceField(queryset=friend_query())
#    ptype = ProtectionType.access_control
#    @classmethod
#    def auth_test(cls, request, data, **kwargs):
#        if request.user.id in data["users"]:
#            return True
#        else:
#            return False
#
#    def __str__(self):
#        return _("Friends")


# @add_protection
class PasswordProtection(BaseProtection):
    name = "pw"
    ptype = ProtectionType.access_control+ProtectionType.authentication

    @classmethod
    def auth(cls, request, data, **kwargs):
        if request.POST.get("password", "") in data["passwords"]:
            return True
        else:
            return False

    def __str__(self):
        return _("Password based authentication")
