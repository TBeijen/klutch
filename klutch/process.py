def process_triggers(client, config):
    """Search for trigger ConfigMap and start sequence.

    Will evaluate the trigger. If it has exceeded max age it will be removed without starting a sequence.

    Args:
        client: Kubernetes client instance
        config: Config instance

    Returns:
        bool: Whether or not there is a sequence ongoing
    """
    return False


def process_ongoing(client, config):
    """Search for current status ConfigMap and act accordingly.

    Either consolidates, or restores autoscalers to their original minReplicas.

    Consolidating will happen based on found status, and will set any HPA to their scaled-up state.
    This means that HPAs reverted by CI/CD deploys will be set back to their scaled-up state within the duration of the control loop.

    Args:
        client: Kubernetes client instance
        config: Config instance

    Returns:
        bool: Whether or not there is a sequence ongoing
    """
    return False


def process_orphans(client, config):
    """Examine HPAs for annotations indicating sequence not finished and restore them to their original state.

    This should do nothing, however there's always the possibility that a status configmap gets accidentally deleted,
    without the HPAs being restored to their original state.

    Args:
        client: Kubernetes client instance
        config: Config instance

    Returns:
        bool: Whether or not there is a sequence ongoing
    """
