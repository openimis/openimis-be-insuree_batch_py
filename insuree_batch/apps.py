from django.apps import AppConfig

MODULE_NAME = "insuree_batch"

DEFAULT_CFG = {
    "gql_query_batch_runs_perms": ["111102"],
    "gql_mutation_create_insuree_batch_perms": ["111101"],
    "template_folder": "openIMIS\\templates\\insuree_batch",
    "insuree_card_template_front_name": "insuree_card_template_front.svg",
    "insuree_card_template_back_name": "insuree_card_template_back.svg",
    "images_on_page": 1,
    "inscape_path": "C:\\Program Files\\Inkscape\\",
    "output_format": "svg"  # Available options are PDF, SVG

}


class InsureeBatchConfig(AppConfig):
    name = MODULE_NAME

    gql_query_batch_runs_perms = []
    gql_mutation_create_insuree_batch_perms = [],
    template_folder = ""
    insuree_card_template_front_name = ""
    insuree_card_template_back_name = ""
    images_on_page = 1
    inscape_path = ""
    output_format = ""

    def _configure_permissions(self, cfg):
        InsureeBatchConfig.gql_query_batch_runs_perms = cfg[
            "gql_query_batch_runs_perms"]
        InsureeBatchConfig.gql_mutation_process_batch_perms = cfg[
            "gql_mutation_create_insuree_batch_perms"]
        InsureeBatchConfig.template_folder = cfg["template_folder"]
        InsureeBatchConfig.insuree_card_template_front_name = cfg[
            "insuree_card_template_front_name"]
        InsureeBatchConfig.insuree_card_template_back_name = cfg[
            "insuree_card_template_back_name"]
        InsureeBatchConfig.images_on_page = cfg["images_on_page"]
        InsureeBatchConfig.inscape_path = cfg["inscape_path"]
        InsureeBatchConfig.output_format = cfg["output_format"]

    def ready(self):
        from core.models import ModuleConfiguration
        cfg = ModuleConfiguration.get_or_default(MODULE_NAME, DEFAULT_CFG)
        self._configure_permissions(cfg)
