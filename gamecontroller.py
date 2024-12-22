#!/usr/bin/env python3

import time
import threading
import signal
import urwid
import pygame
import can

from src.can_utils import discover_node_ids
from src.control import move_odrive_to_position, set_closed_loop_control, set_idle_mode
from src.metrics import get_metrics, METRIC_ENDPOINTS
from src.configure import load_endpoints
from data.button_mappings import (ODRIVE_MAPPING, DEAD_MAN_BUTTON_INDEX, MODE_TOGGLE_BUTTON_INDEX,
                                  FOREARM_UNISON, FOREARM_DIFF)

stop_event = threading.Event()

DEAD_ZONE = 0.25
VELOCITY_SCALING = 3.0
UPDATE_RATE = 30.0

joystick_states = {
    "LB": False,
    "axes": {}
}

class ForearmController:
    def __init__(self, bus, node_id_pair):
        self.bus = bus
        self.node_id_pair = node_id_pair   # [4,5]
        self.unison_val = 0.0
        self.diff_val = 0.0

    def clamp_invert_forearm(self, val, settings):
        v = val
        if settings['invert']:
            v = -v
        return max(settings['min'], min(settings['max'], v))

    def apply_forearm_values(self):
        # In forearm mode, Y=unison, X=diff (already swapped in code below)
        unison = self.clamp_invert_forearm(self.unison_val, FOREARM_UNISON)
        diff = self.clamp_invert_forearm(self.diff_val, FOREARM_DIFF)

        motorA_target = unison + diff
        motorB_target = unison - diff

        # Directly apply these positions (no joint min/max or invert)
        move_odrive_to_position(self.bus, self.node_id_pair[0], motorA_target)
        move_odrive_to_position(self.bus, self.node_id_pair[1], motorB_target)

def clean_shutdown(node_ids, bus, joint_positions):
    print("\nExiting... Moving all ODrives to position 0 and setting them to idle.")
    for i, node_id in enumerate(node_ids):
        try:
            move_odrive_to_position(bus, node_id, 0)
        except Exception as e:
            print(f"[WARNING] Could not set node {node_id} to position 0: {e}")
    time.sleep(2)
    for node_id in node_ids:
        try:
            set_idle_mode(bus, node_id)
        except Exception as e:
            print(f"[WARNING] Error setting node {node_id} to idle: {e}")
    if bus:
        bus.shutdown()

def signal_handler(sig, frame):
    raise KeyboardInterrupt

def handle_input(key, loop, node_ids, bus, joint_positions):
    if key == 'esc':
        stop_event.set()
        raise urwid.ExitMainLoop()

def update_ui_thread(bus, node_ids, endpoints, metrics_text, joystick_text, loop):
    column_widths = {metric: max(len(metric), 4) + 3 for metric in METRIC_ENDPOINTS.keys()}
    node_column_width = 6

    header = f"{'Node':<{node_column_width}}" + "".join(
        f"{name:<{column_widths[name]}}" for name in METRIC_ENDPOINTS.keys()
    )

    possible_deadman_vals = ["Dead-Man", "Pressed", "Not Pressed"]
    deadman_col_width = max(len(v) for v in possible_deadman_vals) + 2
    axis_col_widths = []
    for m in ODRIVE_MAPPING:
        axis_name = m['axis_name']
        axis_col_width = max(len(axis_name), 6) + 2
        axis_col_widths.append(axis_col_width)

    joystick_header_line = f"{'Dead-Man':<{deadman_col_width}}"
    for h, w in zip([m['axis_name'] for m in ODRIVE_MAPPING], axis_col_widths):
        joystick_header_line += f"{h:>{w}}"

    while not stop_event.is_set():
        lines = [header]
        for node_id in node_ids:
            metrics = get_metrics(bus, node_id, endpoints)
            line = f"{node_id:<{node_column_width}}" + "".join(
                f"{(' ' if isinstance(value, (float,int)) and value >= 0 else '') + f'{value:.2f}' if isinstance(value, (float,int)) else f'{value}':<{column_widths[metric]}}"
                for metric, value in metrics.items()
            )
            lines.append(line)
        metrics_text.set_text("\n".join(lines))

        lb_state = "Pressed" if joystick_states["LB"] else "Not Pressed"
        axis_values_line = f"{lb_state:<{deadman_col_width}}"
        for m, w in zip(ODRIVE_MAPPING, axis_col_widths):
            axis_idx = m['joystick_axis']
            axis_val = joystick_states["axes"].get(axis_idx, 0.0)
            formatted_val = f"{axis_val:>6.2f}"
            axis_values_line += f"{formatted_val:>{w}}"

        joystick_lines = [joystick_header_line, axis_values_line]
        joystick_text.set_text("\n".join(joystick_lines))

        time.sleep(0.1)
        try:
            loop.draw_screen()
        except (urwid.ExitMainLoop, RuntimeError):
            break

def apply_dead_zone(val):
    return 0.0 if abs(val) < DEAD_ZONE else val

def joystick_thread_func(bus, node_ids, joint_positions, forearm_ctrl_45, update_rate=30.0):
    clock = pygame.time.Clock()
    velocity_scaling = VELOCITY_SCALING
    joystick = pygame.joystick.Joystick(0)

    while not stop_event.is_set():
        dt = clock.tick(update_rate)/1000.0
        pygame.event.pump()

        lb = joystick.get_button(4) # LB
        rb = joystick.get_button(5) # RB

        joystick_states["LB"] = (lb == 1)

        # Update axes with dead zone and invert RIGHT AFTER READING:
        for m in ODRIVE_MAPPING:
            axis_idx = m['joystick_axis']
            val = 0.0
            if axis_idx < joystick.get_numaxes():
                raw_val = joystick.get_axis(axis_idx)
                raw_val = apply_dead_zone(raw_val)
                if m.get('invert',False):
                    raw_val = -raw_val
                val = raw_val
            joystick_states["axes"][axis_idx] = val

        if lb == 1:
            # Right stick → ODrive2,3 no changes
            m2 = next(x for x in ODRIVE_MAPPING if x['node_index']==2)
            m3 = next(x for x in ODRIVE_MAPPING if x['node_index']==3)
            val2 = joystick_states["axes"].get(m2['joystick_axis'],0.0)
            val3 = joystick_states["axes"].get(m3['joystick_axis'],0.0)

            # Just clamp and move them as original
            joint_positions[2] += val2 * velocity_scaling * dt
            joint_positions[3] += val3 * velocity_scaling * dt
            # ODrive2,3 min/max from ODRIVE_MAPPING
            # In original code we do clamp after increments:
            joint_positions[2] = max(m2['min_position'], min(m2['max_position'], joint_positions[2]))
            joint_positions[3] = max(m3['min_position'], min(m3['max_position'], joint_positions[3]))

            move_odrive_to_position(bus, node_ids[2], joint_positions[2])
            move_odrive_to_position(bus, node_ids[3], joint_positions[3])

            forearm_mode = (rb == 1)

            # Left stick:
            m0 = next(x for x in ODRIVE_MAPPING if x['node_index']==0)
            m1 = next(x for x in ODRIVE_MAPPING if x['node_index']==1)
            lx_val = joystick_states["axes"].get(m0['joystick_axis'],0.0)
            ly_val = joystick_states["axes"].get(m1['joystick_axis'],0.0)

            if not forearm_mode:
                # Shoulder mode unchanged
                joint_positions[0] += lx_val * velocity_scaling * dt
                joint_positions[1] += ly_val * velocity_scaling * dt
                joint_positions[0] = max(m0['min_position'], min(m0['max_position'], joint_positions[0]))
                joint_positions[1] = max(m1['min_position'], min(m1['max_position'], joint_positions[1]))

                move_odrive_to_position(bus, node_ids[0], joint_positions[0])
                move_odrive_to_position(bus, node_ids[1], joint_positions[1])
            else:
                # Forearm mode: Y=unison, X=diff (swapped)
                # ODrive4,5 no joint min/max, no invert from mapping
                # Just update forearm_ctrl_45
                # Y (ly_val) = unison
                # X (lx_val) = diff
                forearm_ctrl_45.unison_val += ly_val * velocity_scaling * dt
                forearm_ctrl_45.diff_val += lx_val * velocity_scaling * dt
                forearm_ctrl_45.apply_forearm_values()
        else:
            # LB not pressed, no movement
            pass

        time.sleep(0.01)

def main():
    signal.signal(signal.SIGINT, signal_handler)

    bus = can.interface.Bus("can0", bustype="socketcan")
    node_ids = list(discover_node_ids(bus))
    endpoints = load_endpoints()

    if not node_ids or len(node_ids)<6:
        print("[ERROR] Need ODrives 0..5 for forearm mode.")
        return

    node_ids.sort()
    print(f"Detected ODrive Node IDs: {node_ids}")

    for node_id in node_ids:
        if not set_closed_loop_control(bus, node_id):
            print(f"[ERROR] Could not set node {node_id} to CLOSED_LOOP_CONTROL. Exiting.")
            bus.shutdown()
            return

    pygame.init()
    pygame.joystick.init()
    if pygame.joystick.get_count() == 0:
        print("[ERROR] No joystick found.")
        pygame.quit()
        return

    joystick = pygame.joystick.Joystick(0)
    joystick.init()
    print(f"Joystick initialized: {joystick.get_name()}")
    print(f"Number of axes: {joystick.get_numaxes()}")

    joint_positions = [m['start_position'] for m in ODRIVE_MAPPING]

    # Forearm controller for ODrive4,5
    forearm_ctrl_45 = ForearmController(bus, [node_ids[4], node_ids[5]])

    metrics_text = urwid.Text("Fetching metrics...", align='left')
    joystick_text = urwid.Text("", align='left')

    metrics_box = urwid.LineBox(metrics_text, title="ODrive Metrics")
    joystick_box = urwid.LineBox(joystick_text, title="Controller Inputs")

    pile = urwid.Pile([metrics_box, joystick_box])
    footer_text = urwid.Text("Press ESC to exit", align='center')
    frame = urwid.Frame(pile, footer=footer_text)

    loop = urwid.MainLoop(
        frame,
        palette=[('reversed', 'standout', '')],
        unhandled_input=lambda key: handle_input(key, loop, node_ids, bus, joint_positions)
    )

    ui_thread = threading.Thread(
        target=update_ui_thread,
        args=(bus, node_ids, endpoints, metrics_text, joystick_text, loop),
        daemon=True
    )
    ui_thread.start()

    joy_thread = threading.Thread(
        target=joystick_thread_func,
        args=(bus, node_ids, joint_positions, forearm_ctrl_45),
        daemon=True
    )  
    joy_thread.start()

    try:
        loop.run()
    except KeyboardInterrupt:
        pass
    finally:
        print("[INFO] Main loop ended, stopping threads...")
        stop_event.set()
        ui_thread.join()
        joy_thread.join()
        print("[INFO] Threads joined, now doing clean shutdown...")
        clean_shutdown(node_ids, bus, joint_positions)
        pygame.quit()

if __name__ == "__main__":
    main()