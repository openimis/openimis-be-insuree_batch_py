import graphene
from django.core.exceptions import PermissionDenied, ValidationError
from django.db import connection
from core import prefix_filterset, ExtendedConnection
from core.schema import OpenIMISMutation, OrderedDjangoFilterConnectionField
from graphene import ObjectType
from django.urls import reverse
from graphene_django import DjangoObjectType
from graphene_django.filter import DjangoFilterConnectionField
from django.contrib.auth.models import AnonymousUser

from location.models import Location
from location.schema import LocationGQLType
from .models import InsureeBatch, BatchInsureeNumber, InsureeBatchMutation
from .apps import InsureeBatchConfig
from django.utils.translation import gettext as _
from django.db.models import Q
import logging

from .services import generate_insuree_numbers

logger = logging.getLogger(__file__)


class InsureeBatchGQLType(DjangoObjectType):
    print_url = graphene.Field(graphene.String)
    export_url = graphene.Field(
        graphene.String, dry_run=graphene.Boolean(), count=graphene.Int()
    )
    nb_generated = graphene.Field(graphene.Int)
    nb_printed = graphene.Field(graphene.Int)

    def resolve_nb_generated(self, info):
        return self.insuree_numbers.count()

    def resolve_nb_printed(self, info):
        return self.insuree_numbers.filter(print_date__isnull=False).count()

    def resolve_print_url(self, info):
        return info.context.build_absolute_uri(
            reverse("batch_qr") + f"?batch={self.id}"
        )

    def resolve_export_url(self, info, count=None, dry_run=False):
        return info.context.build_absolute_uri(
            reverse("export_insurees")
            + f"?batch={self.id}&dryRun={dry_run}&count={count}"
        )

    class Meta:
        model = InsureeBatch
        interfaces = (graphene.relay.Node,)
        filter_fields = {
            "id": ["exact"],
            "run_date": ["exact", "lt", "lte", "gt", "gte"],
            "location": ["isnull"],
            "archived": ["exact"],
            **prefix_filterset("location__", LocationGQLType._meta.filter_fields),
        }
        connection_class = ExtendedConnection


class BatchInsureeNumberGQLType(DjangoObjectType):
    class Meta:
        model = BatchInsureeNumber
        interfaces = (graphene.relay.Node,)
        filter_fields = {
            "id": ["exact"],
            "insuree_number": ["exact"],
            "print_date": ["exact"],
        }
        connection_class = ExtendedConnection


class Query(graphene.ObjectType):
    insuree_batches = OrderedDjangoFilterConnectionField(
        InsureeBatchGQLType,
        client_mutation_id=graphene.String(),
        orderBy=graphene.List(of_type=graphene.String),
    )

    batch_insuree_numbers = OrderedDjangoFilterConnectionField(
        InsureeBatchGQLType, orderBy=graphene.List(of_type=graphene.String)
    )

    def resolve_insuree_batches(self, info, client_mutation_id=None, **kwargs):
        if not info.context.user.has_perms(
            InsureeBatchConfig.gql_query_batch_runs_perms
        ):
            raise PermissionDenied(_("unauthorized"))
        if client_mutation_id:
            queryset = InsureeBatch.objects.filter(
                Q(mutations__mutation__client_mutation_id=client_mutation_id)
            )
        else:
            queryset = InsureeBatch.objects

        return queryset

    def resolve_batch_insuree_numbers(self, info, **kwargs):
        if not info.context.user.has_perms(
            InsureeBatchConfig.gql_query_batch_runs_perms
        ):
            raise PermissionDenied(_("unauthorized"))


class CreateInsureeBatchInputType(OpenIMISMutation.Input):
    comment = graphene.String(required=False)
    amount = graphene.Int(required=True)
    location = graphene.Int(required=False)


class CreateInsureeBatchMutation(OpenIMISMutation):
    """
    Create a new insuree batch
    """

    _mutation_module = "insuree_batch"
    _mutation_class = "CreateInsureeBatchMutation"

    class Input(CreateInsureeBatchInputType):
        pass

    @classmethod
    def async_mutate(cls, user, **data):
        try:
            if type(user) is AnonymousUser or not user.id:
                raise ValidationError(_("mutation.authentication_required"))
            if not user.has_perms(
                InsureeBatchConfig.gql_mutation_create_insuree_batch_perms
            ):
                raise PermissionDenied(_("unauthorized"))
            data["audit_user_id"] = user.id_for_audit
            from core.utils import TimeUtils

            data["validity_from"] = TimeUtils.now()
            client_mutation_id = data.get("client_mutation_id")

            location_id = data.get("location")
            if location_id:
                location = Location.filter_queryset().filter(id=location_id).first()
                if not location:
                    raise ValidationError(_("insureebatch.location_id_not_found"))
            else:
                location = None

            batch = generate_insuree_numbers(
                data.get("amount"),
                user.id_for_audit,
                location=location,
                comment=data.get("comment"),
            )
            InsureeBatchMutation.object_mutated(
                user, client_mutation_id=client_mutation_id, insuree_batch=batch
            )
            return None
        except Exception as exc:
            logger.exception("insuree.mutation.failed_to_create_insuree")
            return [
                {
                    "message": _("insuree.mutation.failed_to_create_insuree"),
                    "detail": str(exc),
                }
            ]


class Mutation(graphene.ObjectType):
    create_insuree_batch = CreateInsureeBatchMutation.Field()
