import can
from src.can_utils import discover_node_ids
from src.configure import *

def main():
    bus = None
    try:
        bus = can.interface.Bus("can0", bustype="socketcan")
        node_ids = discover_node_ids(bus)

        # Load configuration and endpoints
        config_data = load_configuration()
        endpoints = load_endpoints()

        # Iterate through each node and assign motor settings dynamically
        for node_id in node_ids:
            # Determine motor type using pole pairs
            motor_type = get_motor_type(bus, node_id, endpoints)

            # Log which node is being configured and its motor type
            print(f"Configuring node {node_id} with motor type {motor_type}")

            # Apply configuration settings for the detected motor type
            config_settings = config_data[motor_type]["settings"]
            if not setup_odrive(bus, node_id, config_settings, endpoints):
                print("Exiting due to an error in configuring a node.")
                return

            print()  # for cleaner output

    except (can.CanError, OSError, FileNotFoundError, json.JSONDecodeError) as e:
        print(f"Initialization error: {e}")
        return

    finally:
        if bus is not None:
            bus.shutdown()

if __name__ == "__main__":
    main()