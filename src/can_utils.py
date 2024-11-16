import struct
import time
import can

def extract_node_id(arbitration_id):
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

def send_can_message(bus, node_id, command_id, data_format, *data_args):
    try:
        bus.send(can.Message(
            arbitration_id=(node_id << 5 | command_id),
            data=struct.pack(data_format, *data_args),
            is_extended_id=False
        ))
        return True
    
    except Exception as e:
        print(f"Error sending CAN message: {e}")
        return False

def receive_can_message(bus, expected_arbitration_id):
    for msg in bus:
        if msg.arbitration_id == expected_arbitration_id:
            return msg
    return None