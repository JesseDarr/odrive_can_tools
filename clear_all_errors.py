import argparse
import can
import sys
from src.odrive_configurator import *

def clear_errors(bus, node_id, endpoints, clear=True):
    # List of endpoint paths based on ODrive documentation
    error_endpoints = [
        "axis0.active_errors",        # Active errors on the axis
        "axis0.disarm_reason",        # Reason for disarm
    ]

    # Clears or reads errors for the specified ODrive node.
    for error_endpoint in error_endpoints:
        if error_endpoint in endpoints['endpoints']:
            endpoint_id = endpoints['endpoints'][error_endpoint]['id']
            endpoint_type = endpoints['endpoints'][error_endpoint]['type']
            error_value = read_config(bus, node_id, endpoint_id, endpoint_type)

            if error_value:
                print(f"Node {node_id} - {error_endpoint} - Error: {error_value}")
                if clear and "active_errors" in error_endpoint:  # Only clear active errors
                    write_config(bus, node_id, endpoint_id, endpoint_type, 0)
                    print(f"Node {node_id} - {error_endpoint} - Error cleared.")
            else:
                print(f"Node {node_id} - {error_endpoint} - No error.")
        else:
            print(f"Endpoint {error_endpoint} not found in the provided endpoints.")
        print()


def main():
    # Argument parser to handle flags
    parser = argparse.ArgumentParser(description='ODrive Error Reader/Clearer.')
    parser.add_argument('-read', action='store_true', help='Only read the errors without clearing them.')
    args = parser.parse_args()

    try:
        # Initialize CAN bus
        bus = can.interface.Bus("can0", bustype="socketcan")

        # Discover ODrive nodes on the network
        node_ids = discover_node_ids(bus)

        # Load configuration and endpoint data
        _, endpoints = load_configuration_and_endpoints()

        # Clear or read errors for each discovered ODrive node
        for node_id in node_ids:
            print(f"Processing node {node_id}")
            if args.read:
                clear_errors(bus, node_id, endpoints, clear=False)  # Read only
            else:
                clear_errors(bus, node_id, endpoints, clear=True)   # Read and clear

    except (can.CanError, OSError, FileNotFoundError, json.JSONDecodeError) as e:
        print(f"Initialization error: {e}")
        sys.exit("Exiting due to an error.")

    finally:
        # Shutdown the CAN bus on script exit
        if 'bus' in locals() or 'bus' in globals():
            bus.shutdown()

if __name__ == "__main__":
    main()