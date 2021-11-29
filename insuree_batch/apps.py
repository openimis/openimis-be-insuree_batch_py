from django.apps import AppConfig

MODULE_NAME = "insuree_batch"

DEFAULT_CFG = {
    "gql_query_batch_runs_perms": ["111102"],
    "gql_mutation_create_insuree_batch_perms": ["111101"],
}


class InsureeBatchConfig(AppConfig):
    name = MODULE_NAME

    gql_query_batch_runs_perms = []
    gql_mutation_create_insuree_batch_perms = []

    def _configure_permissions(self, cfg):
        InsureeBatchConfig.gql_query_batch_runs_perms = cfg[
            "gql_query_batch_runs_perms"]
        InsureeBatchConfig.gql_mutation_process_batch_perms = cfg[
            "gql_mutation_create_insuree_batch_perms"]

    def ready(self):
        from core.models import ModuleConfiguration
        cfg = ModuleConfiguration.get_or_default(MODULE_NAME, DEFAULT_CFG)
        self._configure_permissions(cfg)
