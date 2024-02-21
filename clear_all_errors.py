import can
import sys
from src.odrive_configurator import *

def clear_errors(bus, node_id, endpoints):
    # List of endpoint paths related to errors
    error_endpoints = [
        "axis0.active_errors", # Add more error endpoints as needed
    ]

    # Clears errors for the specified ODrive node.
    for error_endpoint in error_endpoints:
        endpoint_id = endpoints['endpoints'][error_endpoint]['id']
        endpoint_type = endpoints['endpoints'][error_endpoint]['type']
        error_value = read_config(bus, node_id, endpoint_id, endpoint_type)
        
        if error_value:
            print(f"Node {node_id} - {error_endpoint} - Error: {error_value}")
            write_config(bus, node_id, endpoint_id, endpoint_type, 0)
            print(f"Node {node_id} - {error_endpoint} - Error cleared.")
        else:
            print(f"Node {node_id} - {error_endpoint} - No error.")
        print()

def main():
    # Main function to clear errors from all ODrives on the network.
    try:
        # Initialize CAN bus
        bus = can.interface.Bus("can0", bustype="socketcan")

        # Discover ODrive nodes on the network
        node_ids = discover_node_ids(bus)

        # Load configuration and endpoint data
        _, endpoints = load_configuration_and_endpoints()

        # Clear errors for each discovered ODrive node
        for node_id in node_ids:
            print(f"Processing node {node_id}")
            clear_errors(bus, node_id, endpoints)

    except (can.CanError, OSError, FileNotFoundError, json.JSONDecodeError) as e:
        print(f"Initialization error: {e}")
        sys.exit("Exiting due to an error.")

    finally:
        # Shutdown the CAN bus on script exit
        if 'bus' in locals() or 'bus' in globals():
            bus.shutdown()

if __name__ == "__main__":
    main()