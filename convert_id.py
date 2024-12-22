#!/usr/bin/env python3

import sys
import time
import can
from src.configure import load_endpoints, write_config, save_config
from src.can_utils import send_can_message, discover_node_ids

def main():
    if len(sys.argv) < 3:
        print("Usage: python set_odrive_id.py  old_id  new_id")
        return

    old_id = int(sys.argv[1])
    new_id = int(sys.argv[2])

    bus = can.interface.Bus("can0", bustype="socketcan")
    endpoints = load_endpoints()

    discovered = discover_node_ids(bus)
    if old_id not in discovered:
        print(f"[ERROR] ODrive with ID {old_id} not found on the CAN bus.")
        bus.shutdown()
        return

    print(f"Found ODrive with old ID={old_id}. Changing to new ID={new_id}...")

    node_id_endpoint = endpoints["endpoints"]["axis0.config.can.node_id"]["id"]
    node_id_type     = endpoints["endpoints"]["axis0.config.can.node_id"]["type"]

    write_config(bus, old_id, node_id_endpoint, node_id_type, new_id)
    print("Node ID written. Now saving config...")

    save_config_endpoint = endpoints["endpoints"]["save_configuration"]["id"]
    save_config(bus, old_id, save_config_endpoint)
    print("Config saved. You may reboot or power-cycle for it to fully take effect.")

    bus.shutdown()
    print("Done.")

if __name__ == "__main__":
    main()
