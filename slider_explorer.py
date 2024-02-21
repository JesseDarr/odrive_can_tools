import can
import urwid
import json
import time
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

def main():
    bus = can.interface.Bus("can0", bustype="socketcan")
    node_ids = discover_node_ids(bus, discovery_duration=2)
    
    # Adjust the range for each ODrive based on its position in the list
    sliders = []
    for i, node_id in enumerate(node_ids):
        min_val, max_val = (-2.9, 2.9) if i % 2 == 1 else (-5, 5)
        sliders.append(ODriveSlider(node_id, bus, min_val, max_val))
    
    for node_id in node_ids:
        if not set_closed_loop_control(bus, node_id):
            print(f"Failed to set closed loop control for ODrive {node_id}")
            return

    columns = urwid.Columns([urwid.LineBox(slider) for slider in sliders])
    frame = urwid.Frame(urwid.Filler(columns, valign='top'), footer=urwid.Text("Press ESC to exit", align='center'))

    def handle_input(key):
        if key == 'esc':
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

    urwid.MainLoop(frame, palette=[('reversed', 'standout', '')], unhandled_input=handle_input).run()

    for node_id in node_ids:
        if not move_odrive_to_position(bus, node_id, 0) or not set_idle_mode(bus, node_id):
            print(f"Failed to reset ODrive {node_id}")

    if bus: bus.shutdown()

if __name__ == "__main__":
    main()