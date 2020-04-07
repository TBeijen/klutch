import json
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
    trigger_cm_list = actions.find_triggers(config)

    if not trigger_cm_list:
        logger.debug("No triggers found")
        return False

    trigger_cm = trigger_cm_list.pop(0)
    if trigger_cm_list:
        logger.warning("More than one trigger found. Using most recent. Removing others.")
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
        "Processing trigger ConfigMap (name={}, uid={})".format(trigger_cm.metadata.name, trigger_cm.metadata.uid,)
    )
    status = []
    for hpa in actions.find_hpas(config):
        try:
            patched_hpa = actions.scale_hpa(config, hpa)
            patched_hpa_status = json.loads(patched_hpa.metadata.annotations.get(config.hpa_annotation_status))
            entry = {
                "name": patched_hpa.metadata.name,
                "namespace": patched_hpa.metadata.namespace,
                "status": patched_hpa_status,
            }
            status.append(entry)
        except Exception as e:
            # Allow other hpas to be processed on any (un)expected error
            logger.error(
                "Error while scaling up HorizontalPodAutoscaler (namespace={ns}, name={name}, uid={uid}). Reason: {err}".format(
                    ns=hpa.metadata.namespace, name=hpa.metadata.name, uid=hpa.metadata.uid, err=str(e),
                )
            )
    created_status_cm = actions.create_status(config, status)
    actions.delete_trigger(trigger_cm)
    logger.info(
        "Finished updating {} HorizontalPodAutoscalers. Status written to ConfigMap (name={}, uid={})".format(
            len(status), created_status_cm.metadata.name, created_status_cm.metadata.uid
        )
    )

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
    logger.debug("Looking for status ConfigMap objects.")
    status_cm_list = actions.find_status(config)

    if not status_cm_list:
        logger.debug("No status found")
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
