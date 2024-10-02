import can
import sys
from src.odrive_configurator import *

def configure_node(bus, node_id, config_settings, endpoints):
    # Configure a single ODrive node with specified settings
    try:
        # Check if the ODrive node's firmware and hardware versions match expected values
        # check_firmware_hardware_version(bus, node_id, endpoints['fw_version'], endpoints['hw_version']) # it was very dumb to disable this, I am dumb

        # Iterate through each setting in the configuration and apply it to the ODrive node
        for setting in config_settings:
            path = setting['path']
            value = setting['value']
            configure_odrive(bus, node_id, path, value, endpoints)

        # Save the configuration changes on the ODrive node
        save_endpoint_id = endpoints['endpoints']['save_configuration']['id']
        save_config(bus, node_id, save_endpoint_id)

    except ValueError as e:
        print(f"Error: {e}")
        return False
    except Exception as e:
        print(f"Unexpected error during configuration: {e}")
        return False
    return True

def main():
    bus = None
    try:
        bus = can.interface.Bus("can0", bustype="socketcan")
        node_ids = discover_node_ids(bus, discovery_duration=2)

        config_settings, endpoints = load_configuration_and_endpoints()

        for node_id in node_ids:
            print(f"Configuring node {node_id}")
            if not configure_node(bus, node_id, config_settings, endpoints):
                print("Exiting due to an error in configuring a node.")
                return
            print() # for cleaner output

    except (can.CanError, OSError, FileNotFoundError, json.JSONDecodeError) as e:
        print(f"Initialization error: {e}")
        return

    finally:
        if bus is not None:
            bus.shutdown()

if __name__ == "__main__":
    main()