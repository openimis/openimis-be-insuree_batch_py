import os
from django.http import FileResponse
from django.shortcuts import get_object_or_404

from django.core.exceptions import PermissionDenied
from django.utils.translation import gettext as _

from . import services
from .apps import InsureeBatchConfig
from .models import InsureeBatch


def export_insurees(request):
    if not request.user.has_perms(InsureeBatchConfig.gql_query_batch_runs_perms):
        raise PermissionDenied(_("unauthorized"))

    dry_run = request.GET.get("dryRun", "false").lower() == "true"
    batch_id = request.GET.get("batch")
    amount = request.GET.get("amount")

    if batch_id:
        batch = get_object_or_404(InsureeBatch, id=batch_id)
    else:
        batch = None

    zip_file = services.export_insurees(batch, amount, dry_run)
    response = FileResponse(open(zip_file.name, 'rb'), content_type="application/zip")
    response['Content-Disposition'] = 'attachment; filename=%s' % os.path.basename(zip_file.name)
    response['Content-Length'] = os.path.getsize(zip_file.name)
    return response
