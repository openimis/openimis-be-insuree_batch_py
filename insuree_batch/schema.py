import graphene
from django.core.exceptions import PermissionDenied
from django.db import connection
from core import prefix_filterset, ExtendedConnection
from core.schema import OpenIMISMutation, OrderedDjangoFilterConnectionField
from graphene import ObjectType
from graphene_django import DjangoObjectType
from graphene_django.filter import DjangoFilterConnectionField
from product.schema import ProductGQLType
from location.schema import LocationGQLType
from .models import InsureeBatch, BatchInsureeNumber
from .services import ProcessBatchSubmit, ProcessBatchService
from .apps import ClaimBatchConfig, InsureeBatchConfig
from django.utils.translation import gettext as _


class InsureeBatchGQLType(DjangoObjectType):
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
        orderBy=graphene.List(of_type=graphene.String))
    batch_insuree_numbers = OrderedDjangoFilterConnectionField(
        InsureeBatchGQLType,
        orderBy=graphene.List(of_type=graphene.String))

    def resolve_insuree_batches(self, info, **kwargs):
        if not info.context.user.has_perms(InsureeBatchConfig.gql_query_batch_runs_perms):
            raise PermissionDenied(_("unauthorized"))

    def resolve_batch_insuree_numbers(self, info, **kwargs):
        if not info.context.user.has_perms(ClaimBatchConfig.gql_query_relative_indexes_perms):
            raise PermissionDenied(_("unauthorized"))


class Mutation(graphene.ObjectType):
    pass
    #process_batch = ProcessBatchMutation.Field()
