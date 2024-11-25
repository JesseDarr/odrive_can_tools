from src.can_utils import send_can_message
from src.configure import read_config

def set_idle_mode(bus, node_id):
    try:
        return send_can_message(bus, node_id, 0x07, '<I', 1)  # 0x07: Set_Axis_State, 1: AxisState.IDLE
    except Exception as e:
        print(f"Error setting idle mode for ODrive {node_id}: {e}")
        return False

def set_closed_loop_control(bus, node_id):
    try:
        return send_can_message(bus, node_id, 0x07, '<I', 8)  # 0x07: Set_Axis_State, 8: AxisState.CLOSED_LOOP_CONTROL
    except Exception as e:
        print(f"Error setting closed loop control for ODrive {node_id}: {e}")
        return False

def move_odrive_to_position(bus, node_id, position):
    try:
        return send_can_message(bus, node_id, 0x0c, '<fhh', position, 0, 0)  # 0x0c: Set_Input_Position
    except Exception as e:
        print(f"Error moving ODrive {node_id} to position {position}: {e}")
        return False

def move_odrive_with_torque(bus, node_id, torque):
    try:
        return send_can_message(bus, node_id, 0x0e, '<f', torque)  # 0x0d: Set_Input_Torque
    except Exception as e:
        print(f"Error applying torque to ODrive {node_id}: {e}")
        return False

def get_control_mode(bus, node_id, endpoints):
    """
    Retrieves the control mode (1: position, 2: velocity, 3: torque) for the specified node.
    """
    control_mode_id = endpoints["endpoints"]["axis0.controller.config.control_mode"]["id"]
    control_mode_type = endpoints["endpoints"]["axis0.controller.config.control_mode"]["type"]
    return read_config(bus, node_id, control_mode_id, control_mode_type)