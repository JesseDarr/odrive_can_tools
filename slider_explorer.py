import time
import can
import urwid
import signal
from src.odrive_configurator import discover_node_ids, load_configuration_and_endpoints
from src.odrive_control import set_closed_loop_control, move_odrive_to_position, set_idle_mode

class ODriveSlider(urwid.WidgetWrap):
    def __init__(self, node_ids, bus, min_val, max_val, differential=False):
        self.node_ids = node_ids  # can be a single or list of node_ids
        self.bus = bus
        self.min_val = min_val
        self.max_val = max_val
        self.value = 0.0
        self.differential = differential  # Track if it's a differential slider

        # Slider label, can mention multiple ODrives if necessary
        label = f"ODrive {', '.join(map(str, self.node_ids))}: "
        self.edit = urwid.Edit(label, "0.0")

        # Add the slider to a pile layout
        pile = urwid.Pile([
            self.edit
        ])

        urwid.connect_signal(self.edit, 'change', self.on_edit_change)
        self._w = urwid.AttrMap(pile, None, focus_map='reversed')

    def on_edit_change(self, edit, new_text):
        try:
            value = float(new_text)
            if self.min_val <= value <= self.max_val:
                self.value = value
                self.move_motor()
            else:
                raise ValueError
        except ValueError:
            self.edit.set_edit_text(f"{self.value:.1f}")

    def move_motor(self):
        if self.differential:
            # Move the ODrives in opposite directions (differential)
            move_odrive_to_position(self.bus, self.node_ids[0], self.value)
            move_odrive_to_position(self.bus, self.node_ids[1], -self.value)
        else:
            # Normal movement for single or dual ODrives in unison
            for node_id in self.node_ids:
                if not move_odrive_to_position(self.bus, node_id, self.value):
                    print(f"Failed to move ODrive {node_id} to position {self.value}")

def clean_shutdown(node_ids, bus):
    print("\nExiting... Resetting ODrives to position 0 and setting them to idle.")
    for node_id in node_ids:
        if not move_odrive_to_position(bus, node_id, 0):
            print(f"Failed to reset position for ODrive {node_id}")
   
    time.sleep(5)

    for node_id in node_ids:
        if not set_idle_mode(bus, node_id):
            print(f"Failed to set idle mode for ODrive {node_id}")

    if bus is not None:
        bus.shutdown()

def signal_handler(signal, frame):
    raise KeyboardInterrupt

def handle_input(key, columns, sliders, loop, node_ids, bus):
    if key == 'esc':
        clean_shutdown(node_ids, bus)
        raise urwid.ExitMainLoop()
    elif key in ('up', 'down'):
        focus = columns.focus_position
        slider = sliders[focus]
        if key == 'up' and slider.value < slider.max_val:
            slider.value += 0.1
        elif key == 'down' and slider.value > slider.min_val:
            slider.value -= 0.1
        slider.edit.set_edit_text(f"{slider.value:.1f}")
        slider.move_motor()
    elif key in ('left', 'right'):
        focus = columns.focus_position
        columns.focus_position = max(0, min(len(sliders) - 1, focus + (1 if key == 'right' else -1)))

def main():
    signal.signal(signal.SIGINT, signal_handler)
    bus = can.interface.Bus("can0", bustype="socketcan")
    node_ids = list(discover_node_ids(bus, discovery_duration=2))  # Convert to list

    # First 4 sliders are for individual ODrives
    sliders = [ODriveSlider([node_id], bus, -5, 5) for node_id in node_ids[:4]]

    # Last 2 sliders: one for both ODrives moving together, one for differential motion
    sliders.append(ODriveSlider([node_ids[4], node_ids[5]], bus, -25, 25))  # Unison movement
    sliders.append(ODriveSlider([node_ids[4], node_ids[5]], bus, -25, 25, differential=True))  # Differential movement

    for node_id in node_ids:
        if not set_closed_loop_control(bus, node_id):
            print(f"Failed to set closed loop control for ODrive {node_id}")
            return

    columns = urwid.Columns([urwid.LineBox(slider) for slider in sliders])
    frame = urwid.Frame(urwid.Filler(columns, valign='top'), footer=urwid.Text("Press ESC to exit", align='center'))

    loop = urwid.MainLoop(frame, palette=[('reversed', 'standout', '')], unhandled_input=lambda key: handle_input(key, columns, sliders, loop, node_ids, bus))

    try:
        loop.run()
    except KeyboardInterrupt:
        clean_shutdown(node_ids, bus)
    finally:
        if bus:
            bus.shutdown()

if __name__ == "__main__":
    main()