#!/usr/bin/env python3

import time
import can
import urwid
import signal
from threading import Thread
from src.can_utils import discover_node_ids
from src.control import move_odrive_to_position, set_closed_loop_control, set_idle_mode
from src.metrics import get_metrics, METRIC_ENDPOINTS
from src.configure import load_endpoints


class ShoulderController:
    """
    Controls two ODrives on the same joint, with motors facing opposite directions.
    A single "shoulder_val" from the slider means motorA -> +val, motorB -> -val.
    """
    def __init__(self, bus, node_id_pair, endpoints):
        self.bus = bus
        self.node_id_pair = node_id_pair   # e.g. [1, 2]
        self.endpoints = endpoints
        self.shoulder_val = 0.0

    def apply_shoulder_values(self):
        nodeA, nodeB = self.node_id_pair
        motorA_target = -self.shoulder_val
        motorB_target = self.shoulder_val

        move_odrive_to_position(self.bus, nodeA, motorA_target)
        move_odrive_to_position(self.bus, nodeB, motorB_target)


class ForearmController:
    """
    Existing controller for a forearm that has "unison" and "diff" sliders.
    Now for node [5, 6].
    """
    def __init__(self, bus, node_id_pair, endpoints):
        self.bus = bus
        self.node_id_pair = node_id_pair   # e.g. [5, 6]
        self.endpoints = endpoints
        self.unison_val = 0.0
        self.diff_val = 0.0

    def apply_forearm_values(self):
        nodeA, nodeB = self.node_id_pair
        motorA_target = self.unison_val + self.diff_val
        motorB_target = self.unison_val - self.diff_val

        move_odrive_to_position(self.bus, nodeA, motorA_target)
        move_odrive_to_position(self.bus, nodeB, motorB_target)


class ODriveSlider(urwid.WidgetWrap):
    """
    General slider for controlling either:
      - A single ODrive or normal pair of ODrives,
      - A shared ForearmController in 'unison'/'diff' mode (node5,6),
      - A shared ShoulderController in 'shoulder' mode (node1,2).
    """
    def __init__(self, node_ids, bus, endpoints, min_val, max_val,
                 shared_forearm=None, forearm_mode=None,
                 shared_shoulder=None):
        self.node_ids = node_ids
        self.bus = bus
        self.endpoints = endpoints
        self.min_val = min_val
        self.max_val = max_val
        self.value = 0.0

        self.shared_forearm = shared_forearm
        self.forearm_mode = forearm_mode  # 'unison', 'diff', or None

        self.shared_shoulder = shared_shoulder  # If not None => shoulder joint

        # Decide a label based on the mode
        if self.shared_shoulder:
            label_text = f"Shoulder (Nodes {node_ids[0]}, {node_ids[1]}): {self.value:.1f}"
        elif self.shared_forearm and self.forearm_mode == 'unison':
            label_text = f"Forearm UNISON: {self.value:.1f}"
        elif self.shared_forearm and self.forearm_mode == 'diff':
            label_text = f"Forearm DIFF: {self.value:.1f}"
        else:
            label_text = f"ODrive {', '.join(map(str, self.node_ids))}: {self.value:.1f}"

        self.label = urwid.Text(label_text)
        self.pile = urwid.Pile([self.label])
        super().__init__(urwid.AttrMap(self.pile, None, focus_map='reversed'))

    def update_value(self, increment):
        self.value = max(self.min_val, min(self.max_val, self.value + increment))

        # Update label
        if self.shared_shoulder:
            self.label.set_text(f"Shoulder (Nodes {self.node_ids[0]}, {self.node_ids[1]}): {self.value:.1f}")
        elif self.shared_forearm and self.forearm_mode == 'unison':
            self.label.set_text(f"Forearm UNISON: {self.value:.1f}")
        elif self.shared_forearm and self.forearm_mode == 'diff':
            self.label.set_text(f"Forearm DIFF: {self.value:.1f}")
        else:
            self.label.set_text(f"ODrive {', '.join(map(str, self.node_ids))}: {self.value:.1f}")

        self.move_motor()

    def move_motor(self):
        # If forearm, set unison/diff
        if self.shared_forearm and self.forearm_mode in ['unison', 'diff']:
            if self.forearm_mode == 'unison':
                self.shared_forearm.unison_val = self.value
            else:
                self.shared_forearm.diff_val = self.value
            self.shared_forearm.apply_forearm_values()

        # If shoulder, set the single "shoulder_val"
        elif self.shared_shoulder:
            self.shared_shoulder.shoulder_val = self.value
            self.shared_shoulder.apply_shoulder_values()

        else:
            # Single or normal pair
            for node_id in self.node_ids:
                move_odrive_to_position(self.bus, node_id, self.value)


def clean_shutdown(node_ids, bus):
    print("\nExiting... resetting ODrives to position 0 and setting them to idle.")
    for nd in node_ids:
        move_odrive_to_position(bus, nd, 0)
    time.sleep(2)
    for nd in node_ids:
        set_idle_mode(bus, nd)
    if bus:
        bus.shutdown()

def signal_handler(sig, frame):
    raise KeyboardInterrupt

def handle_input(key, columns, sliders, node_ids, bus):
    if key == 'esc':
        clean_shutdown(node_ids, bus)
        raise urwid.ExitMainLoop()
    elif key in ('up', 'down'):
        # Adjust the slider value
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
    column_widths = {
        metric: max(len(metric), 4) + 3
        for metric in METRIC_ENDPOINTS.keys()
    }
    node_col_width = 6

    # Build the header line
    header = f"{'Node':<{node_col_width}}" + "".join(
        f"{name:<{column_widths[name]}}" for name in METRIC_ENDPOINTS.keys()
    )

    while True:
        lines = [header]
        for nd in node_ids:
            metrics = get_metrics(bus, nd, endpoints)
            line = f"{nd:<{node_col_width}}"
            for metric, val in metrics.items():
                if isinstance(val, (float,int)):
                    sign_space = ' ' if val >= 0 else ''
                    formatted_val = f"{sign_space}{val:.2f}"
                    line += f"{formatted_val:<{column_widths[metric]}}"
                else:
                    # If None or non-numeric => show "None"
                    line += f"{'None':<{column_widths[metric]}}"
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

    node_ids.sort()
    print(f"Detected ODrive Node IDs: {node_ids}")

    # Set each discovered node to CLOSED_LOOP_CONTROL
    for nd in node_ids:
        if not set_closed_loop_control(bus, nd):
            print(f"[ERROR] Could not set node {nd} to CLOSED_LOOP_CONTROL. Exiting.")
            bus.shutdown()
            return

    # Build your sliders logic
    sliders = []

    # Single slider for node 0 (if present)
    if 0 in node_ids:
        sliders.append(ODriveSlider([0], bus, endpoints, -4.8, 4.8))

    # Shoulder: node1,2 => 1 slider with ShoulderController
    if 1 in node_ids and 2 in node_ids:
        shoulder_ctrl = ShoulderController(bus, [1, 2], endpoints)
        slider_shoulder = ODriveSlider(
            [1, 2],
            bus,
            endpoints,
            min_val=-4.8,
            max_val=4.8,
            shared_shoulder=shoulder_ctrl
        )
        sliders.append(slider_shoulder)

    # Single slider for node 3
    if 3 in node_ids:
        sliders.append(ODriveSlider([3], bus, endpoints, -4.8, 4.8))

    # Single slider for node 4
    if 4 in node_ids:
        # new single motor we introduced
        sliders.append(ODriveSlider([4], bus, endpoints, -4.8, 4.8))

    # Forearm: node5,6 => unison/diff
    if 5 in node_ids and 6 in node_ids:
        forearm_ctrl = ForearmController(bus, [5, 6], endpoints)
        slider_unison = ODriveSlider(
            [5, 6],
            bus,
            endpoints,
            min_val=-25,
            max_val=25,
            shared_forearm=forearm_ctrl,
            forearm_mode='unison'
        )
        slider_diff = ODriveSlider(
            [5, 6],
            bus,
            endpoints,
            min_val=-25,
            max_val=25,
            shared_forearm=forearm_ctrl,
            forearm_mode='diff'
        )
        sliders.append(slider_unison)
        sliders.append(slider_diff)

    columns = urwid.Columns([urwid.LineBox(s) for s in sliders])
    metrics_text = urwid.Text("Fetching metrics...", align='left')
    pile = urwid.Pile([columns, metrics_text])
    frame = urwid.Frame(
        urwid.Filler(pile, valign='top'),
        footer=urwid.Text("Press ESC to exit", align='center')
    )

    loop = urwid.MainLoop(
        frame,
        palette=[('reversed', 'standout', '')],
        unhandled_input=lambda k: handle_input(k, columns, sliders, node_ids, bus)
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