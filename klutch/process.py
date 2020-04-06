import logging

from klutch import actions
from klutch.config import Config

logger = logging.getLogger(__name__)


def process_triggers(config: Config):
    """Search for trigger ConfigMap and start sequence.

    Will evaluate the trigger. If it has exceeded max age it will be removed without starting a sequence.

    Args:
        config: Config instance

    Returns:
        bool: Whether or not there is a sequence ongoing
    """
    logger.info("Looking for trigger ConfigMap objects.")
    trigger_cm_list = actions.find_triggers(config)  # noqa: F841
    return False


def process_ongoing(config: Config):
    """Search for current status ConfigMap and act accordingly.

    Either consolidates, or restores autoscalers to their original minReplicas.

    Consolidating will happen based on found status, and will set any HPA to their scaled-up state.
    This means that HPAs reverted by CI/CD deploys will be set back to their scaled-up state within the duration of the control loop.

    Args:
        config: Config instance

    Returns:
        bool: Whether or not there is a sequence ongoing
    """
    return False


def process_orphans(config: Config):
    """Examine HPAs for annotations indicating sequence not finished and restore them to their original state.

    This should do nothing, however there's always the possibility that a status configmap gets accidentally deleted,
    without the HPAs being restored to their original state.

    Args:
        config: Config instance

    Returns:
        bool: Whether or not there is a sequence ongoing
    """
