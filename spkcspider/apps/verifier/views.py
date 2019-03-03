__all__ = ["HashAlgoView", "CreateEntry", "HashAlgoView"]

from django.shortcuts import redirect
from django.core.exceptions import NON_FIELD_ERRORS
from django.views.generic.edit import UpdateView
from django.views.generic.detail import DetailView
from django.views import View
from django.http import HttpResponse, Http404
from django.views.decorators.csrf import csrf_exempt
from django.utils.decorators import method_decorator
from django.conf import settings
from rdflib import Literal

from spkcspider import celery_app
from .models import DataVerificationTag
from .forms import CreateEntryForm
from .validate import validate


@celery_app.task(bind=True, name='async validation')
def async_validate_entry(self, ob):
    return validate(ob, self)


class CreateEntry(UpdateView):
    # NOTE: this class is csrf_exempted
    # reason for this are upload stops and cross post requests
    model = DataVerificationTag
    form_class = CreateEntryForm
    template_name = "spider_verifier/dv_form.html"
    task_id_field = "task_id"
    object = None

    def get_object(self):
        if self.task_id_field not in self.kwargs:
            return None
        result = async_validate_entry.AsyncResult(
            self.kwargs[self.task_id_field]
        )
        if not result:
            raise Http404()
        return result

    # exempt from csrf checks
    # if you want to enable them mark post with csrf_protect
    # this allows enforcing upload limits
    @method_decorator(csrf_exempt)
    def dispatch(self, request, *args, **kwargs):
        return super().dispatch(request, *args, **kwargs)

    def get_form_kwargs(self):
        ret = super().get_form_kwargs()
        if "initial" not in ret:
            # {} not hashable
            ret["initial"] = {}
        ret["initial"]["url"] = self.request.META.get("Referer", "")
        return ret

    def get(self, request, *args, **kwargs):
        self.object = self.get_object()
        form = None
        if self.object:
            if self.object.ready():
                if self.object.successful():
                    ret = redirect(
                        "spider_verifier:hash",
                        hash=self.object.result.instance
                    )
                    ret["Access-Control-Allow-Origin"] = "*"
                    return ret
                # replace form
                form = self.get_form()
                form.add_error(NON_FIELD_ERRORS, self.object.result)
            else:
                self.template_name = "spider_verifier/dv_wait.html"
        else:
            form = self.get_form()
        return self.render_to_response(
            self.get_context_data(form=form, **kwargs)
        )

    def post(self, request, *args, **kwargs):
        """
        Handle POST requests: instantiate a form instance with the passed
        POST variables and then check if it's valid.
        """
        self.object = self.get_object()
        form = None
        if self.object:
            if self.object.ready():
                if self.object.successful():
                    ret = redirect(
                        "spider_verifier:hash",
                        hash=self.object.result.instance
                    )
                    ret["Access-Control-Allow-Origin"] = "*"
                    return ret
                # replace form
                form = self.get_form()
                form.add_error(NON_FIELD_ERRORS, self.object.result)
            else:
                ret = redirect(
                    "spider_verifier:task", task_id=self.object.task_id
                )
                ret["Access-Control-Allow-Origin"] = "*"
                return ret
        else:
            form = self.get_form()
        if form.is_valid():
            return self.form_valid(form)
        else:
            return self.form_invalid(form)

    def form_valid(self, form):
        task = async_validate_entry.apply_async(
            args=(form.save(),)
        )
        ret = redirect(
            "spider_verifier:task", task_id=task.task_id
        )
        ret["Access-Control-Allow-Origin"] = "*"
        return ret


class VerifyEntry(DetailView):
    model = DataVerificationTag
    slug_field = "hash"
    slug_url_kwarg = "hash"
    template_name = "spider_verifier/dv_detail.html"

    def get_context_data(self, **kwargs):
        if self.object.verification_state == "verified":
            if self.object.checked:
                kwargs["verified"] = Literal(self.object.checked)
            else:
                kwargs["verified"] = Literal(True)
        else:
            kwargs["verified"] = Literal(False)
        kwargs["hash_algorithm"] = getattr(
            settings, "VERIFICATION_HASH_ALGORITHM",
            settings.SPIDER_HASH_ALGORITHM
        ).name
        return super().get_context_data(**kwargs)


class HashAlgoView(View):

    def get(self, request, *args, **kwargs):
        algo = getattr(
            settings, "VERIFICATION_HASH_ALGORITHM",
            settings.SPIDER_HASH_ALGORITHM
        ).name
        return HttpResponse(
            content=algo.encode("utf8"),
            content_type="text/plain; charset=utf8"
        )
