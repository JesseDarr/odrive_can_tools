import can
from src.can_utils import discover_node_ids
from src.odrive_configurator import *

def main():
    bus = None
    try:
        bus = can.interface.Bus("can0", bustype="socketcan")
        node_ids = discover_node_ids(bus, discovery_duration=2)

        # Load configuration and endpoints
        config_data = load_configuration()
        endpoints = load_endpoints()

        # Iterate through each node and assign appropriate motor settings
        for idx, node_id in enumerate(node_ids):
            print(f"Configuring node {node_id}")
            
            # Apply 8308 settings for the first 4 nodes, GB36 settings for the last 2 nodes
            if idx < 4:
                config_settings = config_data["8308"]["settings"]
            else:
                config_settings = config_data["GB36"]["settings"]

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