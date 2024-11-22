import time
import can
import urwid
import signal
from src.can_utils import discover_node_ids
from src.odrive_control import set_closed_loop_control, move_odrive_to_position, set_idle_mode

class ODriveSlider(urwid.WidgetWrap):
    def __init__(self, node_ids, bus, min_val, max_val, differential=False):
        self.node_ids = node_ids
        self.bus = bus
        self.min_val = min_val
        self.max_val = max_val
        self.value = 0.0
        self.differential = differential

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
        Sends commands to move the motor(s).
        """
        if self.differential:
            # Differential motion
            move_odrive_to_position(self.bus, self.node_ids[0], self.value)
            move_odrive_to_position(self.bus, self.node_ids[1], -self.value)
        else:
            # Unison or single motor motion
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

def main():
    signal.signal(signal.SIGINT, signal_handler)
    bus = can.interface.Bus("can0", bustype="socketcan")
    node_ids = list(discover_node_ids(bus, discovery_duration=2))

    # Sliders for individual and differential motion
    sliders = [ODriveSlider([node_id], bus, -5, 5) for node_id in node_ids[:4]]
    sliders.append(ODriveSlider([node_ids[4], node_ids[5]], bus, -25, 25))  # Unison
    sliders.append(ODriveSlider([node_ids[4], node_ids[5]], bus, -25, 25, differential=True))  # Differential

    # Set closed-loop control for all nodes
    for node_id in node_ids:
        if not set_closed_loop_control(bus, node_id):
            print(f"Failed to set closed loop control for ODrive {node_id}")
            return

    # Create UI layout
    columns = urwid.Columns([urwid.LineBox(slider) for slider in sliders])
    frame = urwid.Frame(urwid.Filler(columns, valign='top'), footer=urwid.Text("Press ESC to exit", align='center'))
    loop = urwid.MainLoop(frame, palette=[('reversed', 'standout', '')],
                          unhandled_input=lambda key: handle_input(key, columns, sliders, node_ids, bus))

    try:
        loop.run()
    except KeyboardInterrupt:
        clean_shutdown(node_ids, bus)
    finally:
        if bus:
            bus.shutdown()

if __name__ == "__main__":
    main()