from core import fields
from core import models as core_models
from django.db import models
from location import models as location_models


class InsureeBatch(core_models.UUIDModel):
    location = models.ForeignKey(
        location_models.Location, models.DO_NOTHING,
        db_column='LocationId', blank=True, null=True)
    audit_user_id = models.IntegerField(db_column='AuditUserID')
    run_date = fields.DateTimeField(db_column='RunDate', auto_now_add=True)
    archived = models.BooleanField(default=False)
    comment = models.TextField(blank=True, null=True)


class BatchInsureeNumber(core_models.UUIDModel):
    batch = models.ForeignKey(InsureeBatch, on_delete=models.CASCADE, db_index=True, related_name="insuree_numbers")
    insuree_number = models.CharField(db_column='CHFID', max_length=12, blank=True, null=True)
    print_date = models.DateTimeField(blank=True, null=True)
