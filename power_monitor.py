import can
import curses
import time
from src.odrive_configurator import load_configuration_and_endpoints, discover_node_ids, read_config

# Constants for endpoint paths
VOLTAGE_ENDPOINT = "vbus_voltage"
CURRENT_ENDPOINT = "ibus"
UPDATE_INTERVAL = 0.2  # Update interval in seconds

def get_odrive_power(bus, node_id, endpoints):
    # Read voltage and current from the ODrive
    voltage = read_config(bus, node_id, endpoints["endpoints"][VOLTAGE_ENDPOINT]["id"], endpoints["endpoints"][VOLTAGE_ENDPOINT]["type"])
    current = read_config(bus, node_id, endpoints["endpoints"][CURRENT_ENDPOINT]["id"], endpoints["endpoints"][CURRENT_ENDPOINT]["type"])
    
    # Calculate power (watts)
    if voltage is not None and current is not None:
        power = round(voltage * current, 2)
        return voltage, current, power
    else:
        return None, None, None

def monitor_odrive_power(stdscr, bus, node_ids, endpoints):
    # Configure curses
    curses.curs_set(0)  # Hide the cursor
    stdscr.clear()

    # Display headers
    stdscr.addstr(0, 0, f"{'Node ID':<10} {'Voltage (V)':<15} {'Current (A)':<15} {'Power (W)':<15}")
    stdscr.addstr(1, 0, "-" * 55)

    while True:
        try:
            # Update the data for each ODrive node
            for idx, node_id in enumerate(node_ids):
                voltage, current, power = get_odrive_power(bus, node_id, endpoints)
                if voltage is not None:
                    line = f"{node_id:<10} {voltage:<15.2f} {current:<15.2f} {power:<15.2f}"
                else:
                    line = f"{node_id:<10} {'Error':<15} {'Error':<15} {'Error':<15}"
                stdscr.addstr(idx + 2, 0, line.ljust(55))  # Update the corresponding line
            
            stdscr.refresh()
            time.sleep(UPDATE_INTERVAL)
        except KeyboardInterrupt:
            break
        except Exception as e:
            stdscr.addstr(len(node_ids) + 3, 0, f"[ERROR] {e}")
            stdscr.refresh()
            time.sleep(UPDATE_INTERVAL)

def main():
    # Initialize CAN bus
    bus = can.interface.Bus(channel='can0', bustype='socketcan')

    # Load configuration and endpoints
    _, endpoints = load_configuration_and_endpoints()

    # Discover ODrive node IDs
    print("Discovering ODrives on the CAN network...")
    node_ids = discover_node_ids(bus)
    
    if not node_ids:
        print("No ODrives detected on the network.")
        return

    # Launch the curses interface
    curses.wrapper(monitor_odrive_power, bus, node_ids, endpoints)

if __name__ == "__main__":
    main()