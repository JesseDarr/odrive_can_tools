import struct
import can

def extract_node_id(arbitration_id):
    return arbitration_id >> 5

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