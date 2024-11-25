from src.configure import read_config

# Metric endpoints for extensibility
METRIC_ENDPOINTS = {
    "volts":         "vbus_voltage",                             
    "amps":          "ibus",                                     
    "bus_amps":      "axis0.motor.alpha_beta_controller.I_bus",  
    "pos":           "axis0.pos_estimate",                       
    "pos_tgt":       "axis0.controller.input_pos",               
    "vel":           "axis0.vel_estimate",          
    "vel_tgt":       "axis0.controller.input_vel", 
    "tor (Nm)":      "axis0.motor.torque_estimate", 
    "tor_tgt (Nm)":  "axis0.controller.input_torque",
    "mech_pwr (W)":  "axis0.motor.mechanical_power", 
    "elec_pwr (W)":  "axis0.motor.electrical_power", 
    "armed":         "axis0.is_armed",               
    "disarm_msg":    "axis0.disarm_reason"
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