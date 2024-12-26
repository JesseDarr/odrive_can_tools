#!/usr/bin/env python3

import sys
import time
import threading
import signal
import urwid
import can

from src.can_utils import discover_node_ids
from src.control import move_odrive_to_position, set_closed_loop_control, set_idle_mode

stop_event = threading.Event()

UPDATE_RATE = 30.0   # Hz
VELOCITY_SCALING = 3.0

class VelocitySlider(urwid.WidgetWrap):
    def __init__(self, min_val=-30.0, max_val=30.0, step=0.1):
        self.min_val = min_val
        self.max_val = max_val
        self.step = step
        self.value = 0.0
        self.text = urwid.Text(f"Velocity: {self.value:.1f}")
        wrapped = urwid.Filler(self.text, valign='top')
        super().__init__(urwid.LineBox(wrapped, title="Pseudo-Velocity Slider"))

    def increment(self):
        self.value = min(self.max_val, self.value + self.step)
        self.text.set_text(f"Velocity: {self.value:.1f}")

    def decrement(self):
        self.value = max(self.min_val, self.value - self.step)
        self.text.set_text(f"Velocity: {self.value:.1f}")

def signal_handler(sig, frame):
    raise KeyboardInterrupt

def handle_input(key, slider):
    if key == 'up':
        slider.increment()
    elif key == 'down':
        slider.decrement()
    elif key == 'esc':
        stop_event.set()
        raise urwid.ExitMainLoop()

def motor_update_thread(bus, node_id, slider):
    current_position = 0.0
    dt = 1.0 / UPDATE_RATE
    while not stop_event.is_set():
        current_position += slider.value * dt
        try:
            move_odrive_to_position(bus, node_id, current_position)
        except:
            pass
        time.sleep(dt)

def clean_shutdown(bus, node_id):
    print("[INFO] Setting ODrive to IDLE...")
    try:
        set_idle_mode(bus, node_id)
    except Exception as e:
        print(f"[WARNING] Error setting node {node_id} to IDLE: {e}")
    bus.shutdown()

def main():
    signal.signal(signal.SIGINT, signal_handler)

    if len(sys.argv) < 2:
        print("Usage: python test_slider_velocity.py <node_id>")
        return

    node_id = int(sys.argv[1])

    bus = can.interface.Bus("can0", bustype="socketcan")
    discovered = discover_node_ids(bus)
    if node_id not in discovered:
        print(f"[ERROR] Node {node_id} not found on CAN bus.")
        bus.shutdown()
        return

    if not set_closed_loop_control(bus, node_id):
        print(f"[ERROR] Could not set node {node_id} to CLOSED_LOOP_CONTROL.")
        bus.shutdown()
        return

    print(f"[INFO] Node {node_id} in CLOSED_LOOP_CONTROL (position mode).")

    slider = VelocitySlider()
    ui_thread = threading.Thread(
        target=motor_update_thread,
        args=(bus, node_id, slider),
        daemon=True
    )
    ui_thread.start()

    def unhandled(key):
        handle_input(key, slider)

    loop = urwid.MainLoop(slider, unhandled_input=unhandled)

    try:
        loop.run()
    except KeyboardInterrupt:
        pass
    finally:
        print("[INFO] Exiting, stopping threads...")
        stop_event.set()
        ui_thread.join()
        clean_shutdown(bus, node_id)

if __name__ == "__main__":
    main()