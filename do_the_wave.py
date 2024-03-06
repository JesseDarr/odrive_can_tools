import can
import json
import time
import sys
from src.odrive_configurator import discover_node_ids
from src.odrive_control import set_closed_loop_control, move_odrive_to_position, set_idle_mode
from select import select

def main():
    bus = None
    try:
        bus = can.interface.Bus("can0", bustype="socketcan")
        node_ids = discover_node_ids(bus, discovery_duration=2)

        for node_id in node_ids:
            if not set_closed_loop_control(bus, node_id):
                print(f"Failed to set closed loop control for ODrive {node_id}")
                return

        user_input = input("Enter oscillation amplitude (0 to 3 turns) for ODrives: ")
        try:
            amplitude = float(user_input)
            if amplitude < 0 or amplitude > 3:
                print("Amplitude out of range. Exiting.")
                return
        except ValueError:
            print("Invalid input. Exiting.")
            return

        # Oscillate motors
        while True:
            for sign in [1, -1]:
                position = sign * amplitude
                for node_id in node_ids:
                    if not move_odrive_to_position(bus, node_id, position):
                        print(f"Failed to move ODrive {node_id} to position {position}")
                        return

                # Check for user input to exit
                if select([sys.stdin], [], [], 0.5)[0]:
                    input()  # Clear input buffer
                    print("Input detected. Exiting.")
                    return
                time.sleep(0.5)  # Adjust delay for oscillation speed

    except (can.CanError, OSError, FileNotFoundError, json.JSONDecodeError) as e:
        print(f"Initialization error: {e}")

    finally:
        # First, reset the positions of all ODrives to 0
        for node_id in node_ids:
            if not move_odrive_to_position(bus, node_id, 0):
                print(f"Failed to reset position for ODrive {node_id}")
        time.sleep(2)

        # Then, set all ODrives to idle mode
        for node_id in node_ids:
            if not set_idle_mode(bus, node_id):
                print(f"Failed to set idle mode for ODrive {node_id}")

        if bus is not None:
            bus.shutdown()


if __name__ == "__main__":
    main()