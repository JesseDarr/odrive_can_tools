import struct
import can
from src.can_utils import send_can_message, receive_can_message

def set_idle_mode(bus, node_id):
    try:
        # Put axis into idle state
        return send_can_message(bus, node_id, 0x07, '<I', 1) # 0x07: Set_Axis_State, 1: AxisState.IDLE
    except Exception as e:
        print(f"Error setting idle mode for ODrive {node_id}: {e}")
        return False

def set_closed_loop_control(bus, node_id):
    try:
        # Put axis into closed loop control state
        return send_can_message(bus, node_id, 0x07, '<I', 8) # 0x07: Set_Axis_State, 8: AxisState.CLOSED_LOOP_CONTROL
    except Exception as e:
        print(f"Error setting closed loop control for ODrive {node_id}: {e}")
        return False

def move_odrive_to_position(bus, node_id, position):
    try:
        # Set position
        return send_can_message(bus, node_id, 0x0c, '<fhh', position, 0, 0) # 0x0c: Set_Input_Position
    except Exception as e:
        print(f"Error moving ODrive {node_id} to position {position}: {e}")
        return False