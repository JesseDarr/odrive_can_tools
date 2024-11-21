from src.odrive_configurator import read_config

# Metric endpoints for extensibility
METRIC_ENDPOINTS = {
    "voltage": "vbus_voltage",
    "current": "ibus"
    # Add additional metrics here
}

def get_metrics(bus, node_id, endpoints):
    """
    Retrieves all metrics for a specific ODrive node.
    Returns a dictionary of metrics with values or None for failed metrics.
    """
    metrics = {}
    for metric_name, endpoint_key in METRIC_ENDPOINTS.items():
        try:
            metrics[metric_name] = read_config(
                bus,
                node_id,
                endpoints["endpoints"][endpoint_key]["id"],
                endpoints["endpoints"][endpoint_key]["type"]
            )
        except Exception as e:
            print(f"[ERROR] Failed to retrieve {metric_name} for node {node_id}: {e}")
            metrics[metric_name] = "None"
    return metrics
