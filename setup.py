#!/usr/bin/env python3

import can
from src.can_utils import discover_node_ids
from src.configure import *

# Node-to-motor map
MOTOR_MAP = {
    0: "8308",
    1: "8308",
    2: "8308",
    3: "8308",
    4: "8308",
    5: "GB36",
    6: "GB36",
    7: "5208"
}

def main():
    bus = None
    try:
        bus = can.interface.Bus("can0", bustype="socketcan")
        node_ids = discover_node_ids(bus)

        # Load configuration and endpoints
        config_data = load_configuration()
        endpoints = load_endpoints()

        # Iterate through each node
        for node_id in node_ids:
            # Determine motor type from MOTOR_MAP
            motor_type = MOTOR_MAP.get(node_id)
            if motor_type is None:
                print(f"[WARNING] No known motor mapping for node {node_id}. Skipping...")
                continue

            # Log which node is being configured and its motor type
            print(f"Configuring node {node_id} with motor type '{motor_type}'")

            # Apply configuration settings for the mapped motor type
            config_settings = config_data[motor_type]["settings"]
            if not setup_odrive(bus, node_id, config_settings, endpoints):
                print("Exiting due to an error in configuring a node.")
                return

            print()  # For cleaner output

    except (can.CanError, OSError, FileNotFoundError, json.JSONDecodeError) as e:
        print(f"Initialization error: {e}")
        return

    finally:
        if bus is not None:
            bus.shutdown()

if __name__ == "__main__":
    main()