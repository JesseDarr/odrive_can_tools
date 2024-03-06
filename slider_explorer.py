import time
import can
import urwid
import signal
from src.odrive_configurator import discover_node_ids
from src.odrive_control import set_closed_loop_control, move_odrive_to_position, set_idle_mode

class ODriveSlider(urwid.WidgetWrap):
    def __init__(self, node_id, bus, min_val, max_val):
        self.node_id, self.bus, self.min_val, self.max_val = node_id, bus, min_val, max_val
        self.value = 0.0
        self.edit = urwid.Edit(f"ODrive {node_id}: ", "0.0")
        urwid.connect_signal(self.edit, 'change', self.on_edit_change)
        self._w = urwid.AttrMap(self.edit, None, focus_map='reversed')

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
        if not move_odrive_to_position(self.bus, self.node_id, self.value):
            print(f"Failed to move ODrive {self.node_id} to position {self.value}")

def clean_shutdown(node_ids, bus):
    print("\nExiting... Resetting ODrives to position 0 and setting them to idle.")
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

def signal_handler(signal, frame):
    raise KeyboardInterrupt

def handle_input(key, columns, sliders, loop, node_ids, bus):
    if key == 'esc':
        clean_shutdown(node_ids, bus)  # Call clean_shutdown here before exiting
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
    signal.signal(signal.SIGINT, signal_handler)  # Catch CTRL+C signal
    bus = can.interface.Bus("can0", bustype="socketcan")
    node_ids = discover_node_ids(bus, discovery_duration=2)
    
    sliders = [ODriveSlider(node_id, bus, -5, 5) for node_id in node_ids]
    
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
        if bus: bus.shutdown()

if __name__ == "__main__":
    main()