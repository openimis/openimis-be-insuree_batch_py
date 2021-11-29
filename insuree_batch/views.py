from django.core.exceptions import PermissionDenied
from django.utils.translation import gettext as _
from .apps import InsureeBatchConfig


def report(request):
    if not request.user.has_perms(InsureeBatchConfig.account_preview_perms):
        raise PermissionDenied(_("unauthorized"))
    return "foo"
