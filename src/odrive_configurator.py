# odrive_configurator.py
import json
import os
import struct
import time
from src.can_utils import send_can_message, receive_can_message

# Constants for ODrive CAN operations
READ  = 0x00
RXSDO = 0x04
TXSDO = 0x05
WRITE = 0x01

# Data type formats for CAN messages
format_lookup = {
    'bool': '?', 'uint8': 'B', 'int8': 'b',
    'uint16': 'H', 'int16': 'h', 'uint32': 'I', 'int32': 'i',
    'uint64': 'Q', 'int64': 'q', 'float': 'f'
}

def load_configuration_and_endpoints():
    # Load configuration and endpoint data from JSON
    script_dir     = os.path.dirname(os.path.abspath(__file__))
    json_path      = os.path.join(script_dir, '..', 'data', 'config.json')
    endpoints_path = os.path.join(script_dir, '..', 'data', 'flat_endpoints.json')

    with open(json_path, 'r') as f:
        config_json = json.load(f)
    config_settings = config_json['settings']

    with open(endpoints_path, 'r') as f:
        endpoints = json.load(f)

    return config_settings, endpoints

def extract_node_id(arbitration_id):
    # Extract the node ID from a CAN arbitration ID
    return arbitration_id >> 5

def discover_node_ids(bus, discovery_duration=5):
    # Discover ODrive node IDs on the CAN network
    while bus.recv(timeout=0) is not None: pass
    end_time = time.time() + discovery_duration
    node_ids = set()

    while time.time() < end_time:
        msg = bus.recv(timeout=1)
        if msg: node_ids.add(extract_node_id(msg.arbitration_id))

    # Print the number of discovered ODrives
    print(f"Discovered {len(node_ids)} ODrive(s) on the network:")
    print()

    return node_ids

def read_config(bus, node_id, endpoint_id, endpoint_type):
    # Read a configuration value from an ODrive node
    send_can_message(bus, node_id, RXSDO, '<BHB', READ, endpoint_id, 0)
    response = receive_can_message(bus, node_id << 5 | TXSDO)
    if response:
        _, _, _, value = struct.unpack_from('<BHB' + format_lookup[endpoint_type], response.data)
        return value
    else:
        print("[ERROR] No response received in read_config.")
        return None

def write_config(bus, node_id, endpoint_id, endpoint_type, value):
    # Write a configuration value to an ODrive node
    send_can_message(bus, node_id, RXSDO, '<BHB' + format_lookup[endpoint_type], WRITE, endpoint_id, 0, value)

def validate_config(bus, node_id, endpoint_id, endpoint_type, expected_value):
    # Validate a configuration value on an ODrive node
    actual_value = read_config(bus, node_id, endpoint_id, endpoint_type)
    return actual_value == expected_value

def configure_odrive(bus, node_id, path, value, endpoints):
    endpoint_id = endpoints['endpoints'][path]['id']
    endpoint_type = endpoints['endpoints'][path]['type']

    current_value = read_config(bus, node_id, endpoint_id, endpoint_type)
    if isinstance(current_value, float):
        current_value = round(current_value, 3)

    if current_value != value:
        write_config(bus, node_id, endpoint_id, endpoint_type, value)
        if not validate_config(bus, node_id, endpoint_id, endpoint_type, value):
            print(f"    Node {node_id} - {path:50} - new: {value:<7} - cur: {current_value:<7} - status: update failed")
            return False
        else:
            print(f"    Node {node_id} - {path:50} - new: {value:<7} - cur: {current_value:<7} - status: update success")
            return True
    else:
        print(f"    Node {node_id} - {path:50} - new: {value:<7} - cur: {current_value:<7} - status: already set")
        return True


def save_config(bus, node_id, save_endpoint_id):
    # Send a command to save the current configuration on an ODrive node
    send_can_message(bus, node_id, RXSDO, '<BHB', WRITE, save_endpoint_id, 0)
    print(f"Configuration saved for node {node_id}")

def check_firmware_hardware_version(bus, node_id, fw_version_expected, hw_version_expected):
    # Check the firmware and hardware version of an ODrive node
    send_can_message(bus, node_id, READ, '')
    response = receive_can_message(bus, node_id << 5 | READ)
    if response:
        _, hw_product_line, hw_version, hw_variant, fw_major, fw_minor, fw_revision, fw_unreleased = struct.unpack('<BBBBBBBB', response.data)
        fw_version_actual = f"{fw_major}.{fw_minor}.{fw_revision}"
        hw_version_actual = f"{hw_product_line}.{hw_version}.{hw_variant}"

        if fw_version_actual != fw_version_expected or hw_version_actual != hw_version_expected:
            raise ValueError(f"Node {node_id} version mismatch. Firmware: {fw_version_actual} - Expected: {fw_version_expected}, Hardware: {hw_version_actual} - Expected: {hw_version_expected}")
    else:
        print(f"[ERROR] No response received when checking firmware and hardware version for node {node_id}.")

def handle_errors(bus, node_id, error_endpoints):
    # Reads and clears errors for the specified ODrive node.
    for endpoint in error_endpoints:
        endpoint_id = endpoint['id']
        endpoint_type = endpoint['type']
        error_value = read_config(bus, node_id, endpoint_id, endpoint_type)

        if error_value:
            print(f"Node {node_id} - {endpoint['path']} - Error: {error_value}")
            # Clear the error by writing zero
            write_config(bus, node_id, endpoint_id, endpoint_type, 0)
            print(f"Node {node_id} - {endpoint['path']} - Error cleared.")
        else:
            print(f"Node {node_id} - {endpoint['path']} - No error detected.")