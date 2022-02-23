from django.apps import AppConfig

MODULE_NAME = "insuree_batch"

DEFAULT_CFG = {
    "gql_query_batch_runs_perms": ["111102"],
    "gql_mutation_create_insuree_batch_perms": ["111101"],
    "template_folder": "templates/insuree_batch",
    "front_template_name": "front.svg",
    "images_on_page": 1,
    "inkscale_path": "C:\\Program Files\\Inkscape\\"

}


class InsureeBatchConfig(AppConfig):
    name = MODULE_NAME

    gql_query_batch_runs_perms = []
    gql_mutation_create_insuree_batch_perms = [],
    template_folder = ""
    front_template_name = ""
    images_on_page = 1
    inkscale_path = ""

    def _configure_permissions(self, cfg):
        InsureeBatchConfig.gql_query_batch_runs_perms = cfg[
            "gql_query_batch_runs_perms"]
        InsureeBatchConfig.gql_mutation_process_batch_perms = cfg[
            "gql_mutation_create_insuree_batch_perms"]
        InsureeBatchConfig.template_folder = cfg["template_folder"]
        InsureeBatchConfig.front_template_name = cfg["front_template_name"]
        InsureeBatchConfig.images_on_page = cfg["images_on_page"]
        InsureeBatchConfig.inkscale_path = cfg["inkscale_path"]

    def ready(self):
        from core.models import ModuleConfiguration
        cfg = ModuleConfiguration.get_or_default(MODULE_NAME, DEFAULT_CFG)
        self._configure_permissions(cfg)
