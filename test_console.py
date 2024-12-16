import time
import can
import urwid
import signal
from threading import Thread
from src.can_utils import discover_node_ids
from src.control import *
from src.metrics import get_metrics, METRIC_ENDPOINTS
from src.configure import load_endpoints

class ForearmController:

    def __init__(self, bus, node_id_pair, endpoints):
        self.bus = bus
        self.node_id_pair = node_id_pair   # e.g. [4, 5]
        self.endpoints = endpoints
        self.unison_val = 0.0
        self.diff_val = 0.0

    def apply_forearm_values(self):
        nodeA, nodeB = self.node_id_pair
        motorA_target = self.unison_val + self.diff_val
        motorB_target = self.unison_val - self.diff_val

        # Because control mode is always position, we just move to position:
        move_odrive_to_position(self.bus, nodeA, motorA_target)
        move_odrive_to_position(self.bus, nodeB, motorB_target)


class ODriveSlider(urwid.WidgetWrap):
    def __init__(self, node_ids, bus, endpoints, min_val, max_val,
                 shared_forearm=None, forearm_mode=None):
        """
        If 'shared_forearm' is None, this slider controls one or more motors normally.
        If it's not None, 'forearm_mode' is 'unison' or 'diff'. 
        """
        self.node_ids = node_ids
        self.bus = bus
        self.endpoints = endpoints
        self.min_val = min_val
        self.max_val = max_val
        self.value = 0.0

        self.shared_forearm = shared_forearm
        self.forearm_mode = forearm_mode  # can be None, 'unison', or 'diff'

        # Slider label text
        if self.forearm_mode == 'unison':
            label_text = f"Forearm UNISON: {self.value:.1f}"
        elif self.forearm_mode == 'diff':
            label_text = f"Forearm DIFF: {self.value:.1f}"
        else:
            label_text = f"ODrive {', '.join(map(str, self.node_ids))}: {self.value:.1f}"
        self.label = urwid.Text(label_text)

        self.pile = urwid.Pile([self.label])
        self._w = urwid.AttrMap(self.pile, None, focus_map='reversed')

    def update_value(self, increment):
        """
        Adjust slider value on arrow key press.
        """
        self.value = max(self.min_val, min(self.max_val, self.value + increment))

        # Update label
        if self.forearm_mode == 'unison':
            self.label.set_text(f"Forearm UNISON: {self.value:.1f}")
        elif self.forearm_mode == 'diff':
            self.label.set_text(f"Forearm DIFF: {self.value:.1f}")
        else:
            self.label.set_text(f"ODrive {', '.join(map(str, self.node_ids))}: {self.value:.1f}")

        self.move_motor()

    def move_motor(self):
        """
        If slider is part of the forearm, we update the shared ForearmController
        and call apply_forearm_values(). Otherwise, move the motor(s) directly.
        """
        if self.shared_forearm and self.forearm_mode in ['unison', 'diff']:
            if self.forearm_mode == 'unison':
                self.shared_forearm.unison_val = self.value
            else:  # 'diff'
                self.shared_forearm.diff_val = self.value

            # Apply combined forearm values now
            self.shared_forearm.apply_forearm_values()

        else:
            # Single or pair of motors in normal mode
            for node_id in self.node_ids:
                move_odrive_to_position(self.bus, node_id, self.value)


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
    """
    Keybindings: up/down to adjust slider value, left/right to switch slider focus, ESC to exit.
    """
    if key == 'esc':
        clean_shutdown(node_ids, bus)
        raise urwid.ExitMainLoop()
    elif key in ('up', 'down'):
        focus = columns.focus_position
        slider = sliders[focus]
        increment = 0.1 if key == 'up' else -0.1
        slider.update_value(increment)
    elif key in ('left', 'right'):
        focus = columns.focus_position
        if key == 'right' and focus < len(sliders) - 1:
            columns.focus_position += 1
        elif key == 'left' and focus > 0:
            columns.focus_position -= 1

def update_metrics_textbox(bus, node_ids, endpoints, metrics_text, loop):
    """
    Background thread updates the metrics display periodically.
    """
    column_widths = {
        metric: max(len(metric), 4) + 3
        for metric in METRIC_ENDPOINTS.keys()
    }
    node_column_width = 6
    header = f"{'Node':<{node_column_width}}" + "".join(
        f"{name:<{column_widths[name]}}" for name in METRIC_ENDPOINTS.keys()
    )

    while True:
        lines = [header]
        for node_id in node_ids:
            metrics = get_metrics(bus, node_id, endpoints)
            line = f"{node_id:<{node_column_width}}" + "".join(
                f"{(' ' if isinstance(value, (float,int)) and value >= 0 else '') + f'{value:.2f}' if isinstance(value, (float,int)) else f'{value}':<{column_widths[metric]}}"
                for metric, value in metrics.items()
            )
            lines.append(line)

        metrics_text.set_text("\n".join(lines))
        time.sleep(0.1)
        loop.draw_screen()

def main():
    signal.signal(signal.SIGINT, signal_handler)
    bus = can.interface.Bus("can0", bustype="socketcan")
    node_ids = list(discover_node_ids(bus))
    endpoints = load_endpoints()

    if not node_ids:
        print("No ODrives detected on the CAN network. Exiting.")
        return

    # Sort for consistent ordering
    node_ids.sort()
    print(f"Detected ODrive Node IDs: {node_ids}")

    # Force each discovered node to CLOSED_LOOP_CONTROL with position mode
    for node_id in node_ids:
        if not set_closed_loop_control(bus, node_id):
            print(f"[ERROR] Could not set node {node_id} to CLOSED_LOOP_CONTROL. Exiting.")
            bus.shutdown()
            return

    # Build UI sliders
    sliders = []

    # Example: If you have exactly 6 Node IDs
    if len(node_ids) == 6:
        # Single motor sliders for first 4 nodes
        for node_id in node_ids[:4]:
            sliders.append(ODriveSlider([node_id], bus, endpoints, -5, 5))

        # Last 2 nodes form the "forearm" pair
        forearm_node_pair = [node_ids[4], node_ids[5]]
        forearm_ctrl = ForearmController(bus, forearm_node_pair, endpoints)

        # Slider #5: Unison
        unison_slider = ODriveSlider(
            forearm_node_pair,    # node pair
            bus,
            endpoints,
            min_val=-25,
            max_val=25,
            shared_forearm=forearm_ctrl,
            forearm_mode='unison'
        )
        # Slider #6: Differential
        diff_slider = ODriveSlider(
            forearm_node_pair,    # node pair
            bus,
            endpoints,
            min_val=-25,
            max_val=25,
            shared_forearm=forearm_ctrl,
            forearm_mode='diff'
        )
        sliders.append(unison_slider)
        sliders.append(diff_slider)

    else:
        # If fewer or more than 6, just create an individual slider for each node
        for node_id in node_ids:
            sliders.append(ODriveSlider([node_id], bus, endpoints, -5, 5))

    columns = urwid.Columns([urwid.LineBox(slider) for slider in sliders])
    metrics_text = urwid.Text("Fetching metrics...", align='left')
    pile = urwid.Pile([columns, metrics_text])
    frame = urwid.Frame(
        urwid.Filler(pile, valign='top'),
        footer=urwid.Text("Press ESC to exit", align='center')
    )

    loop = urwid.MainLoop(
        frame,
        palette=[('reversed', 'standout', '')],
        unhandled_input=lambda key: handle_input(key, columns, sliders, node_ids, bus)
    )

    # Start metrics update thread
    Thread(
        target=update_metrics_textbox,
        args=(bus, node_ids, endpoints, metrics_text, loop),
        daemon=True
    ).start()

    try:
        loop.run()
    except KeyboardInterrupt:
        clean_shutdown(node_ids, bus)
    finally:
        if bus:
            bus.shutdown()

if __name__ == "__main__":
    main()