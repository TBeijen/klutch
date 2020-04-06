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
    logger.debug("Looking for trigger ConfigMap objects.")
    trigger_cm_list = actions.find_triggers(config)  # noqa: F841

    if not trigger_cm_list:
        logger.debug("No triggers found")
        return False

    trigger_cm = trigger_cm_list.pop(0)
    if trigger_cm_list:
        logger.warning(
            "More than one trigger found. Using most recent. Removing others."
        )
        for t in trigger_cm_list:
            actions.delete_trigger(t)

    if not actions.validate_trigger(config, trigger_cm):
        actions.delete_trigger(trigger_cm)
        logger.warning(
            "Trigger ConfigMap (name={}, uid={}) is not valid (expired) and has been deleted.".format(
                trigger_cm.metadata.name, trigger_cm.metadata.uid,
            )
        )
        return False

    logger.info(
        "Processing trigger ConfigMap (name={}, uid={})".format(
            trigger_cm.metadata.name, trigger_cm.metadata.uid,
        )
    )
    status = []
    for hpa in actions.find_hpas(config):
        entry = {
            "name": hpa.metadata.name,
            "namespace": hpa.metadata.namespace,
            "data": {
                "originalMinReplicas": 123,
                "originalCurrentReplicas": 123,
                "appliedMinReplicas": 123,
                "appliedAt": "some-date-time",
            },
        }
        status.append(entry)
        pass

    # TODO: Write status
    # TODO: Delete trigger

    return True


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
