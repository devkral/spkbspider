from django import template
from ..constants.static import namespace_spkcspider

register = template.Library()


@register.simple_tag()
def namespace(ob):
    if isinstance(ob, str):
        nname = ob
    else:
        nname = ob._meta.model_name

    return namespace_spkcspider[nname]