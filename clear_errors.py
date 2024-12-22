#!/usr/bin/env python3

import argparse
import json
import can
import sys
from src.can_utils import discover_node_ids
from src.configure import load_endpoints, clear_errors

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
        endpoints = load_endpoints()

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