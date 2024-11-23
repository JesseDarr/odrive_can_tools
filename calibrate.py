import time
import can
from src.odrive_configurator import load_endpoints, read_config
from src.odrive_control import set_idle_mode
from src.can_utils import discover_node_ids, send_can_message

CALIBRATION_STATE = 3  # AXIS_STATE_ENCODER_OFFSET_CALIBRATION
IDLE_STATE        = 1  # AXIS_STATE_IDLE
CLOSED_LOOP_STATE = 8  # AXIS_STATE_CLOSED_LOOP_CONTROL

def calibrate_motor(bus, node_id, endpoints):
    """
    Runs encoder offset calibration for a single motor and waits for it to complete.
    """
    try:
        print(f"Starting calibration for node {node_id}...")

        # Send calibration command
        send_can_message(bus, node_id, 0x07, '<I', CALIBRATION_STATE)

        # Endpoint details for axis0.current_state
        state_endpoint_id = endpoints["endpoints"]["axis0.current_state"]["id"]
        state_endpoint_type = endpoints["endpoints"]["axis0.current_state"]["type"]

        # Wait for the calibration process to complete
        start_time = time.time()
        timeout = 15  # Allow up to 15 seconds for calibration

        while time.time() - start_time < timeout:
            # Query the current state
            state = read_config(bus, node_id, state_endpoint_id, state_endpoint_type)
            if state == IDLE_STATE:
                print(f"Node {node_id} calibration completed successfully.")
                return True
            elif state == CALIBRATION_STATE:
                print(f"Node {node_id} is still calibrating...")
            else:
                print(f"[INFO] Node {node_id} is in unexpected state {state}. Waiting...")
            time.sleep(1)  # Poll every second

        print(f"[ERROR] Node {node_id} did not complete calibration within {timeout} seconds.")
        return False
    except Exception as e:
        print(f"[ERROR] Calibration error for node {node_id}: {e}")
        return False

def safe_calibrate_all_motors():
    """
    Safely calibrates all motors on the CAN network.
    """
    try:
        bus = can.interface.Bus("can0", bustype="socketcan")
        print("Discovering ODrives on the CAN network...")
        node_ids = discover_node_ids(bus)
        print(f"Discovered {len(node_ids)} ODrive(s) on the network:\n")

        # Load endpoints for calibration
        endpoints = load_endpoints()

        for node_id in node_ids:
            print(f"Preparing to calibrate node {node_id}.")
            input("Ensure it is safe to proceed with calibration. Press Enter to continue...")

            set_idle_mode(bus, node_id)  # Ensure node is in IDLE mode
            if calibrate_motor(bus, node_id, endpoints):  # Pass endpoints to calibrate_motor
                print(f"Node {node_id} successfully calibrated.\n")
            else:
                print(f"[ERROR] Calibration failed for node {node_id}. Moving to the next node.\n")

        print("Calibration process completed.")
    except Exception as e:
        print(f"[ERROR] Calibration process encountered an error: {e}")
    finally:
        if 'bus' in locals() or 'bus' in globals():
            bus.shutdown()

if __name__ == "__main__":
    safe_calibrate_all_motors()
