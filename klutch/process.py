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
    trigger_cm_list = actions.find_cm_triggers(config)

    if not trigger_cm_list:
        logger.debug("No triggers found")
        return False

    trigger_cm = trigger_cm_list.pop(0)
    if trigger_cm_list:
        logger.warning("More than one trigger found. Using most recent. Removing others.")
        for t in trigger_cm_list:
            actions.delete_cm_trigger(t)

    if not actions.validate_cm_trigger(config, trigger_cm):
        actions.delete_cm_trigger(trigger_cm)
        logger.warning(
            "Trigger ConfigMap (name={}, uid={}) is not valid (expired) and has been deleted.".format(
                trigger_cm.metadata.name,
                trigger_cm.metadata.uid,
            )
        )
        return False

    # ==== Above is re-implemented

    logger.info(
        "Processing trigger ConfigMap (name={}, uid={})".format(
            trigger_cm.metadata.name,
            trigger_cm.metadata.uid,
        )
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
                    ns=hpa.metadata.namespace,
                    name=hpa.metadata.name,
                    uid=hpa.metadata.uid,
                    err=str(e),
                )
            )
    created_status_cm = actions.create_status(config, status)
    actions.delete_cm_trigger(trigger_cm)
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

    status_cm = status_cm_list.pop(0)
    if status_cm_list:
        logger.warning("More than one status ConfigMap found. Using most recent. Ignoring others.")

    scaled_hpas = json.loads(status_cm.data.get("status"))
    if not actions.is_status_duration_expired(config, status_cm):
        logger.info("Sequence ongoing. Reconciling HPAs.")
        for h in scaled_hpas:
            name = h.get("name")
            namespace = h.get("namespace")
            try:
                actions.reconcile_hpa(
                    config=config, name=name, namespace=namespace, klutch_hpa_status=h.get("status")
                )
            except Exception as e:
                logger.error(
                    "Error while reconciling HorizontalPodAutoscaler (namespace={ns}, name={name}). Reason: {err}".format(
                        ns=namespace,
                        name=name,
                        err=str(e),
                    )
                )
        return True
    else:
        logger.info("Sequence duration expired. Reverting HPAs.")
        for h in scaled_hpas:
            name = h.get("name")
            namespace = h.get("namespace")
            try:
                actions.revert_hpa(config=config, name=name, namespace=namespace, klutch_hpa_status=h.get("status"))
            except Exception as e:
                logger.error(
                    "Error while reverting HorizontalPodAutoscaler (namespace={ns}, name={name}). Reason: {err}".format(
                        ns=namespace,
                        name=name,
                        err=str(e),
                    )
                )
        actions.delete_status(status_cm)
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
    logger.info("Searching for orphan HorizontalPodAutoscalers that need to be reverted.")
    if actions.find_status(config=config):
        raise RuntimeError("Can not process orphans if status exists.")
    for hpa in actions.find_hpas(config):
        if config.hpa_annotation_status in hpa.metadata.annotations:
            name = hpa.metadata.name
            ns = hpa.metadata.namespace
            logger.warning(
                f"Found HorizontalPodAutoscaler (namespace={ns}, name={name}) having status annotation, reverting."
            )
            actions.revert_hpa(
                config=config,
                name=name,
                namespace=ns,
                klutch_hpa_status=json.loads(hpa.metadata.annotations.get(config.hpa_annotation_status)),
            )
