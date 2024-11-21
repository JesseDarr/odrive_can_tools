import can
import curses
import time
from src.can_utils import discover_node_ids
from src.odrive_configurator import load_endpoints
from src.odrive_metrics import get_metrics

UPDATE_INTERVAL = 0.2  # Update interval in seconds

def monitor_odrive_power(stdscr, bus, node_ids, endpoints):
    """
    Continuously monitor and display ODrive metrics in a curses-based interface.
    """
    curses.curs_set(0)  # Hide the cursor
    stdscr.clear()

    # Convert node_ids to a list for indexing
    node_ids = list(node_ids)

    # Prepare headers
    metrics_sample = get_metrics(bus, node_ids[0], endpoints) if node_ids else {}
    header_row = f"{'Node ID':<10} " + " ".join([f"{metric_name.capitalize():<15}" for metric_name in metrics_sample.keys()])
    stdscr.addstr(0, 0, header_row)
    stdscr.addstr(1, 0, "-" * len(header_row))

    while True:
        try:
            # Update the data for each ODrive node
            row_offset = 2  # Start displaying data after the headers
            for node_id in node_ids:
                try:
                    metrics = get_metrics(bus, node_id, endpoints)
                    line = f"{node_id:<10} " + " ".join(
                        [f"{value:<15.2f}" if isinstance(value, (int, float)) else str(value) for value in metrics.values()]
                    )
                    stdscr.addstr(row_offset, 0, line.ljust(len(header_row)))  # Pad to avoid overlapping
                except Exception as e:
                    # Handle per-node errors to avoid stopping the loop
                    error_message = f"{node_id:<10} Error reading metrics"
                    stdscr.addstr(row_offset, 0, error_message)
                row_offset += 1

            stdscr.refresh()
            time.sleep(UPDATE_INTERVAL)
        except KeyboardInterrupt:
            break  # Gracefully exit on Ctrl+C
        except Exception as e:
            # Display global errors, but continue looping
            stdscr.addstr(len(node_ids) + 3, 0, f"[ERROR] {e}".ljust(len(header_row)))
            stdscr.refresh()
            time.sleep(UPDATE_INTERVAL)

def main():
    """
    Main entry point for the power monitor script.
    """
    try:
        # Initialize CAN bus
        bus = can.interface.Bus(channel='can0', bustype='socketcan')

        # Load endpoints
        endpoints = load_endpoints()

        # Discover ODrive node IDs
        print("Discovering ODrives on the CAN network...")
        node_ids = discover_node_ids(bus)

        if not node_ids:
            print("No ODrives detected on the network.")
            return

        # Launch the curses interface
        curses.wrapper(monitor_odrive_power, bus, node_ids, endpoints)
    except KeyboardInterrupt:
        print("\nMonitor stopped by user.")
    except Exception as e:
        print(f"[ERROR] {e}")


if __name__ == "__main__":
    main()