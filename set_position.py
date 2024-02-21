import can
import json
from src.odrive_configurator import discover_node_ids
from src.odrive_control import set_closed_loop_control, move_odrive_to_position, set_idle_mode

def main():
    bus = None
    try:
        bus = can.interface.Bus("can0", bustype="socketcan")
        node_ids = discover_node_ids(bus, discovery_duration=2)

        for node_id in node_ids:
            if not set_closed_loop_control(bus, node_id):
                print(f"Failed to set closed loop control for ODrive {node_id}")
                return

        while True:
            user_input = input("Enter position (in turns) for ODrives or 'exit' to quit: ")
            if user_input.lower() == 'exit':
                break

            try:
                position = float(user_input)
                for node_id in node_ids:
                    if not move_odrive_to_position(bus, node_id, position):
                        print(f"Failed to move ODrive {node_id} to position {position}")
                        return

            except ValueError:
                print("Non-numeric value entered, exiting.")
                break

    except (can.CanError, OSError, FileNotFoundError, json.JSONDecodeError) as e:
        print(f"Initialization error: {e}")

    finally:
        for node_id in node_ids:
            if not set_idle_mode(bus, node_id):
                print(f"Failed to set idle mode for ODrive {node_id}")

        if bus is not None:
            bus.shutdown()

if __name__ == "__main__":
    main()