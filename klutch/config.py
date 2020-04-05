import argparse


class Config:

    debug = False
    dry_run = False
    interval = 10  # seconds
    cooldown = 300  # seconds
    namespace = None

    cm_trigger_label = "klutch.it/trigger"
    cm_status_label = "klutch.it/status"
    hpa_annotation_enabled = "klutch.it/enabled"
    hpa_annotation_scale_perc_of_actual = "klutch.it/scale-percentage-of-actual"

    def __init__(self, args):
        self.debug = args.debug
        self.dry_run = args.dry_run
        if args.namespace:
            self.namespace = args.namespace
        else:
            self.namespace = open(
                "/var/run/secrets/kubernetes.io/serviceaccount/namespace"
            ).read()


def _get_args(args):
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--debug", help="Debug mode", action="store_true",
    )
    parser.add_argument(
        "--dry-run", help="Do not change anything", action="store_true",
    )
    parser.add_argument(
        "--namespace",
        help="Namespace to store status in. By default will use the namespace klutch is deployed in. (Required when running out of cluster)",
    )
    return parser.parse_args(args)


def get_config(args=None):
    return Config(_get_args(args))
