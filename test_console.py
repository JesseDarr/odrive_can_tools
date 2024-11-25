import time
import can
import urwid
import signal
from threading import Thread
from src.can_utils import discover_node_ids
from src.control import *
from src.metrics import get_metrics, METRIC_ENDPOINTS
from src.configure import load_endpoints

class ODriveSlider(urwid.WidgetWrap):
    def __init__(self, node_ids, bus, endpoints, min_val, max_val, differential=False):
        self.node_ids = node_ids
        self.bus = bus
        self.endpoints = endpoints  # Store endpoints for use in control mode queries
        self.min_val = min_val
        self.max_val = max_val
        self.value = 0.0
        self.differential = differential

        # Retrieve and store the control mode for the slider
        self.control_mode = {}
        for node_id in self.node_ids:
            self.control_mode[node_id] = get_control_mode(self.bus, node_id, self.endpoints)
            print(f"Node {node_id} initialized in control mode: {self.control_mode[node_id]}")

        # Slider label
        self.label = urwid.Text(f"ODrive {', '.join(map(str, self.node_ids))}: {self.value:.1f}")
        self.pile = urwid.Pile([self.label])
        self._w = urwid.AttrMap(self.pile, None, focus_map='reversed')

    def update_value(self, increment):
        """
        Updates the slider value and moves the motor(s).
        """
        self.value = max(self.min_val, min(self.max_val, self.value + increment))
        self.label.set_text(f"ODrive {', '.join(map(str, self.node_ids))}: {self.value:.1f}")
        self.move_motor()

    def move_motor(self):
        """
        Sends commands to move the motor(s) based on the control mode and differential setting.
        """
        if self.differential:
            if self.control_mode[self.node_ids[0]] == 3:  # Position control mode
                move_odrive_to_position(self.bus, self.node_ids[0], self.value)
                move_odrive_to_position(self.bus, self.node_ids[1], -self.value)
            elif self.control_mode[self.node_ids[0]] == 1:  # Torque control mode
                move_odrive_with_torque(self.bus, self.node_ids[0], self.value)
                move_odrive_with_torque(self.bus, self.node_ids[1], -self.value)
            else:
                print(f"Node {self.node_ids[0]} is in an unsupported control mode.")
        else:
            for node_id in self.node_ids:
                if self.control_mode[node_id] == 3:  # Position control mode
                    move_odrive_to_position(self.bus, node_id, self.value)
                elif self.control_mode[node_id] == 1:  # Torque control mode
                    move_odrive_with_torque(self.bus, node_id, self.value)
                else:
                    print(f"Node {node_id} is in an unsupported control mode.")


def clean_shutdown(node_ids, bus):
    print("\nExiting... Resetting ODrives to position 0 and setting them to idle.")
    for node_id in node_ids:
        move_odrive_to_position(bus, node_id, 0)
    time.sleep(2)
    for node_id in node_ids:
        set_idle_mode(bus, node_id)
    if bus:
        bus.shutdown()

def signal_handler(signal, frame):
    raise KeyboardInterrupt

def handle_input(key, columns, sliders, node_ids, bus):
    if key == 'esc':
        clean_shutdown(node_ids, bus)
        raise urwid.ExitMainLoop()
    elif key in ('up', 'down'):
        # Increment or decrement the slider value
        focus = columns.focus_position
        slider = sliders[focus]
        increment = 0.1 if key == 'up' else -0.1
        slider.update_value(increment)
    elif key in ('left', 'right'):
        # Safeguard to prevent out-of-bounds navigation
        focus = columns.focus_position
        if key == 'right' and focus < len(sliders) - 1:
            columns.focus_position += 1
        elif key == 'left' and focus > 0:
            columns.focus_position -= 1

def update_metrics_textbox(bus, node_ids, endpoints, metrics_text, loop):
    """
    Continuously update the metrics display with dynamically determined column widths for each metric.
    """
    # Dynamically calculate the column width for each metric
    column_widths = {
        metric: max(len(metric), 4) + 3  # Enforce minimum length of 4, plus padding of 3
        for metric in METRIC_ENDPOINTS.keys()
    }

    # Add a fixed width for the 'Node' column
    node_column_width = 6  # "Node" + padding

    # Prepare the header row
    header = f"{'Node':<{node_column_width}}" + "".join(
        f"{name:<{column_widths[name]}}" for name in METRIC_ENDPOINTS.keys()
    )

    while True:
        lines = [header]
        for node_id in node_ids:
            metrics = get_metrics(bus, node_id, endpoints)

            # Prepare row with values aligned under each header column
            line = f"{node_id:<{node_column_width}}" + "".join(
                f"{(' ' if value >= 0 else '') + f'{value:.2f}':<{column_widths[metric]}}" if isinstance(value, (int, float)) else f"{'None':<{column_widths[metric]}}"
                for metric, value in metrics.items()
            )
            lines.append(line)

        # Update the textbox with the new lines
        metrics_text.set_text("\n".join(lines))
        time.sleep(0.1)
        loop.draw_screen()

def main():
    signal.signal(signal.SIGINT, signal_handler)
    bus = can.interface.Bus("can0", bustype="socketcan")
    node_ids = list(discover_node_ids(bus))
    endpoints = load_endpoints()  # Load endpoints to pass into sliders

    # Sliders for individual and differential motion
    sliders = [ODriveSlider([node_id], bus, endpoints, -5, 5) for node_id in node_ids[:4]]
    sliders.append(ODriveSlider([node_ids[4], node_ids[5]], bus, endpoints, -25, 25))  # Unison
    sliders.append(ODriveSlider([node_ids[4], node_ids[5]], bus, endpoints, -25, 25, differential=True))  # Differential

    # Set closed-loop control for all nodes
    for node_id in node_ids:
        if not set_closed_loop_control(bus, node_id):
            print(f"Failed to set closed loop control for ODrive {node_id}")
            return

    # Create UI layout
    columns = urwid.Columns([urwid.LineBox(slider) for slider in sliders])
    metrics_text = urwid.Text("Fetching metrics...", align='left')
    pile = urwid.Pile([columns, metrics_text])  # Combine columns and metrics_text in a pile
    frame = urwid.Frame(urwid.Filler(pile, valign='top'), footer=urwid.Text("Press ESC to exit", align='center'))
    loop = urwid.MainLoop(frame, palette=[('reversed', 'standout', '')], unhandled_input=lambda key: handle_input(key, columns, sliders, node_ids, bus))

    # Start metrics update thread
    Thread(target=update_metrics_textbox, args=(bus, node_ids, endpoints, metrics_text, loop), daemon=True).start()

    try:
        loop.run()
    except KeyboardInterrupt:
        clean_shutdown(node_ids, bus)
    finally:
        if bus:
            bus.shutdown()

if __name__ == "__main__":
    main()