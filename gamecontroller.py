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

# ------------------------------------------------------------------------------
# 1) Button and Axis Definitions
# ------------------------------------------------------------------------------
DEAD_MAN_BUTTON_INDEX   = 4  # LB
MODE_TOGGLE_BUTTON_INDEX = 5 # RB

AXIS_LEFT_X       = 0  # Bend
AXIS_LEFT_Y       = 1  # Rotate
AXIS_LEFT_TRIGGER = 2  # <--- New: Left Trigger
AXIS_RIGHT_X      = 3
AXIS_RIGHT_Y      = 4
AXIS_RIGHT_TRIGGER= 5  # <--- New: Right Trigger

UPDATE_RATE              = 30.0
DEAD_ZONE                = 0.25
VELOCITY_SCALING         = 2.0
FOREARM_VELOCITY_SCALING = 1.0
GRIPPER_SCALING          = 0.5

# ------------------------------------------------------------------------------
# 2) Joint Range Definitions
#    Node0 => Joint 0
#    Node(1,2) => Joint 1 (Shoulder)
#    Node3 => Joint 2
#    Node4 => Joint 3
#    Node(5,6) => Gripper (bend + rotate)
#    Node(7) => Gripper squeeze/release
# ------------------------------------------------------------------------------
JOINT0_MIN, JOINT0_MAX = -4.8,  4.8
JOINT1_MIN, JOINT1_MAX = -5.0,  0.0
JOINT2_MIN, JOINT2_MAX = -5.0,  5.0
JOINT3_MIN, JOINT3_MAX = -5.9,  0.0


BEND_MIN,   BEND_MAX     =  -5.0,  5.0
ROTATE_MIN, ROTATE_MAX   = -10.0, 10.0
TRIGGER_MIN, TRIGGER_MAX =  -0.05, 0.7

stop_event = threading.Event()

# We'll store joystick states for UI display
joystick_states = {
    "LB": False,
    "axes": {
        AXIS_LEFT_X:  0.0,
        AXIS_LEFT_Y:  0.0,
        AXIS_RIGHT_X: 0.0,
        AXIS_RIGHT_Y: 0.0,
        AXIS_LEFT_TRIGGER:  0.0,  # <--- For debugging display
        AXIS_RIGHT_TRIGGER: 0.0   # <--- For debugging display
    }
}

# ------------------------------------------------------------------------------
# 3) Helper Functions
# ------------------------------------------------------------------------------
def apply_dead_zone(value):
    return 0.0 if abs(value) < DEAD_ZONE else value

def signal_handler(sig, frame):
    raise KeyboardInterrupt

def handle_input(key, loop, node_ids, bus, joint_positions):
    if key == 'esc':
        stop_event.set()
        raise urwid.ExitMainLoop()

def clean_shutdown(node_ids, bus, joint_positions):
    print("\nExiting... Setting discovered ODrives to pos=0 => IDLE => shutdown.")
    for nid in node_ids:
        try:
            move_odrive_to_position(bus, nid, 0)
        except Exception as e:
            print(f"[WARN] Could not move node {nid} to 0: {e}")
    time.sleep(2)
    for nid in node_ids:
        try:
            set_idle_mode(bus, nid)
        except Exception as e:
            print(f"[WARN] Could not set node {nid} to IDLE: {e}")
    if bus:
        bus.shutdown()

# ------------------------------------------------------------------------------
# 4) Shoulder & Gripper Classes
# ------------------------------------------------------------------------------
class ShoulderController:
    """
    Node(1,2) => single shoulder joint with two motors in opposite directions.
    We track 'value' => motorA = +value, motorB = -value.
    """
    def __init__(self, bus, node_ids):
        self.bus      = bus
        self.node_ids = node_ids
        self.value    = 0.0

    def apply(self):
        nA, nB = self.node_ids
        motorA = self.value
        motorB = -self.value
        move_odrive_to_position(self.bus, nA, motorA)
        move_odrive_to_position(self.bus, nB, motorB)

class GripperController:
    """
    Node(5,6) => 'gripper' with bend_pos and rotate_pos, each in [-7..7].
    No final clamping or coupling logic. If bend=7 and rotate=7, 
    motorA=+14, motorB=0 is allowed, or any other combination.
    """
    def __init__(self, bus, node_ids):
        self.bus        = bus
        self.node_ids   = node_ids  # [5,6]
        self.bend_pos   = 0.0
        self.rotate_pos = 0.0

    def clamp(self, val, min_val, max_val):
        return max(min_val, min(max_val, val))

    def apply(self):
        # compute final motor commands
        motorA = self.rotate_pos + self.bend_pos
        motorB = self.rotate_pos - self.bend_pos

        print(f"[Gripper Debug] bend={self.bend_pos:.2f}, rotate={self.rotate_pos:.2f},"
              f" A={motorA:.2f}, B={motorB:.2f}")

        nA, nB = self.node_ids
        move_odrive_to_position(self.bus, nA, motorA)
        move_odrive_to_position(self.bus, nB, motorB)

# ------------------------------------------------------------------------------
# 5) UI Update Thread
# ------------------------------------------------------------------------------
def update_ui_thread(bus, node_ids, endpoints, metrics_text, joystick_text, loop):
    col_widths = {}
    for metric in METRIC_ENDPOINTS:
        col_widths[metric] = max(len(metric), 4) + 3

    node_col_w = 6
    header = f"{'Node':<{node_col_w}}" + "".join(
        f"{m:<{col_widths[m]}}" for m in METRIC_ENDPOINTS
    )

    axis_names = ["LeftX", "LeftY", "RightX", "RightY", "LTrig", "RTrig"]
    axis_col_w = max(len(n) for n in axis_names) + 3
    joy_header_line = "LB".ljust(8) + "".join(x.ljust(axis_col_w) for x in axis_names)

    while not stop_event.is_set():
        # ODrive metrics
        lines = [header]
        for nid in node_ids:
            data = get_metrics(bus, nid, endpoints)
            row = f"{nid:<{node_col_w}}"
            for metric in METRIC_ENDPOINTS:
                val = data.get(metric, None)
                if isinstance(val, (int, float)):
                    sign_space = ' ' if val >= 0 else ''
                    row += f"{sign_space}{val:.2f}".ljust(col_widths[metric])
                else:
                    row += f"{'None':<{col_widths[metric]}}"
            lines.append(row)
        metrics_text.set_text("\n".join(lines))

        # Joystick line
        lb_str = "Pressed" if joystick_states["LB"] else "NotPress"
        joy_line = lb_str.ljust(8)

        # We display the 6 axes we track
        axis_values = [
            joystick_states["axes"].get(AXIS_LEFT_X, 0.0),
            joystick_states["axes"].get(AXIS_LEFT_Y, 0.0),
            joystick_states["axes"].get(AXIS_RIGHT_X, 0.0),
            joystick_states["axes"].get(AXIS_RIGHT_Y, 0.0),
            joystick_states["axes"].get(AXIS_LEFT_TRIGGER, 0.0),
            joystick_states["axes"].get(AXIS_RIGHT_TRIGGER, 0.0),
        ]
        for val in axis_values:
            joy_line += f"{val:>6.2f}".ljust(axis_col_w)

        joystick_text.set_text(joy_header_line + "\n" + joy_line)

        time.sleep(0.1)
        try:
            loop.draw_screen()
        except (urwid.ExitMainLoop, RuntimeError):
            break

# ------------------------------------------------------------------------------
# 6) Main Joystick Logic Thread
# ------------------------------------------------------------------------------
def joystick_thread_func(
    bus, node_ids, joint_positions,
    shoulder_ctrl, gripper_ctrl,
    update_rate = UPDATE_RATE
):
    """
    - If LB pressed and not RB => normal joints
    - If LB pressed and RB => 'gripper mode'
      * we update both bend and rotate simultaneously, each clamped in [-7..7].
    - Final motor commands can exceed ±7 => we do not clamp them.
    - We do not skip or scale or pin => truly independent axes.
    """
    clock = pygame.time.Clock()
    joystick = pygame.joystick.Joystick(0)
    joystick.init()

    while not stop_event.is_set():
        dt = clock.tick(update_rate) / 1000.0
        pygame.event.pump()

        lb = joystick.get_button(DEAD_MAN_BUTTON_INDEX)
        rb = joystick.get_button(MODE_TOGGLE_BUTTON_INDEX)
        joystick_states["LB"] = bool(lb)

        # Left stick: X => bend, Y => rotate
        raw_bend   = apply_dead_zone(joystick.get_axis(AXIS_LEFT_X))
        raw_rotate = apply_dead_zone(joystick.get_axis(AXIS_LEFT_Y))

        # Right stick
        rx = apply_dead_zone(joystick.get_axis(AXIS_RIGHT_X))
        ry = apply_dead_zone(joystick.get_axis(AXIS_RIGHT_Y))

        # New triggers
        raw_lt = apply_dead_zone(joystick.get_axis(AXIS_LEFT_TRIGGER))
        raw_rt = apply_dead_zone(joystick.get_axis(AXIS_RIGHT_TRIGGER))

        joystick_states["axes"][AXIS_LEFT_X]       = raw_bend
        joystick_states["axes"][AXIS_LEFT_Y]       = raw_rotate
        joystick_states["axes"][AXIS_RIGHT_X]      = rx
        joystick_states["axes"][AXIS_RIGHT_Y]      = ry
        joystick_states["axes"][AXIS_LEFT_TRIGGER] = raw_lt
        joystick_states["axes"][AXIS_RIGHT_TRIGGER] = raw_rt

        if lb:
            # Possibly controlling the normal joints or the gripper
            gripper_mode = (rb == 1)

            # Joint 2 => node3 => Right Stick X
            if 3 in node_ids:
                joint_positions[2] += (rx * VELOCITY_SCALING * dt)
                if joint_positions[2] < JOINT2_MIN:
                    joint_positions[2] = JOINT2_MIN
                if joint_positions[2] > JOINT2_MAX:
                    joint_positions[2] = JOINT2_MAX
                move_odrive_to_position(bus, 3, joint_positions[2])

            # Joint 3 => node4 => Right Stick Y
            if 4 in node_ids:
                joint_positions[3] -= (ry * VELOCITY_SCALING * dt)
                if joint_positions[3] < JOINT3_MIN:
                    joint_positions[3] = JOINT3_MIN
                if joint_positions[3] > JOINT3_MAX:
                    joint_positions[3] = JOINT3_MAX
                move_odrive_to_position(bus, 4, joint_positions[3])

            if not gripper_mode:
                # Normal left-stick => Joint 0 (node0) & Joint 1 (node1,2)
                if 0 in node_ids:
                    joint_positions[0] += (raw_bend * VELOCITY_SCALING * dt)
                    if joint_positions[0] < JOINT0_MIN:
                        joint_positions[0] = JOINT0_MIN
                    if joint_positions[0] > JOINT0_MAX:
                        joint_positions[0] = JOINT0_MAX
                    move_odrive_to_position(bus, 0, joint_positions[0])

                if shoulder_ctrl and (1 in node_ids) and (2 in node_ids):
                    new_val = shoulder_ctrl.value + (raw_rotate * VELOCITY_SCALING * dt)
                    if new_val < JOINT1_MIN:
                        new_val = JOINT1_MIN
                    if new_val > JOINT1_MAX:
                        new_val = JOINT1_MAX
                    shoulder_ctrl.value = new_val
                    shoulder_ctrl.apply()

            else:
                # Gripper mode => node5,6
                if gripper_ctrl and (5 in node_ids) and (6 in node_ids):
                    # We simply update bend_pos and rotate_pos simultaneously
                    # Clamped to [-7..7].
                    new_bend = gripper_ctrl.bend_pos + (raw_bend * VELOCITY_SCALING * FOREARM_VELOCITY_SCALING * dt)
                    new_rotate = gripper_ctrl.rotate_pos + (raw_rotate * VELOCITY_SCALING * FOREARM_VELOCITY_SCALING * dt)

                    if new_bend < BEND_MIN:
                        new_bend = BEND_MIN
                    if new_bend > BEND_MAX:
                        new_bend = BEND_MAX
                    if new_rotate < ROTATE_MIN:
                        new_rotate = ROTATE_MIN
                    if new_rotate > ROTATE_MAX:
                        new_rotate = ROTATE_MAX

                    gripper_ctrl.bend_pos   = new_bend
                    gripper_ctrl.rotate_pos = new_rotate
                    gripper_ctrl.apply()

            # Always handle the 'trigger-driven' ODrive (node7) if present
            if 7 in node_ids:
                new_pos = joint_positions[7]

                # Pressing left trigger => move negative
                if raw_lt > 0:
                    new_pos -= raw_lt * VELOCITY_SCALING * GRIPPER_SCALING * dt

                # Pressing right trigger => move positive
                if raw_rt > 0:
                    new_pos += raw_rt * VELOCITY_SCALING * GRIPPER_SCALING * dt

                # Clamp in [TRIGGER_MIN, TRIGGER_MAX]
                if new_pos < TRIGGER_MIN:
                    new_pos = TRIGGER_MIN
                elif new_pos > TRIGGER_MAX:
                    new_pos = TRIGGER_MAX

                joint_positions[7] = new_pos
                move_odrive_to_position(bus, 7, joint_positions[7])

        time.sleep(0.01)

# ------------------------------------------------------------------------------
# 7) Main Function
# ------------------------------------------------------------------------------
def main():
    signal.signal(signal.SIGINT, signal_handler)

    bus = can.interface.Bus("can0", bustype = "socketcan")
    discovered = list(discover_node_ids(bus))
    endpoints  = load_endpoints()

    if not discovered:
        print("[ERROR] No ODrives found on the CAN bus.")
        return

    discovered.sort()
    print(f"Discovered ODrive Node IDs: {discovered}")

    # Set each discovered node to closed-loop
    for nid in discovered:
        if not set_closed_loop_control(bus, nid):
            print(f"[ERROR] Could not set node {nid} to CLOSED_LOOP_CONTROL.")
            bus.shutdown()
            return

    pygame.init()
    pygame.joystick.init()
    if pygame.joystick.get_count() == 0:
        print("[ERROR] No joystick found.")
        pygame.quit()
        return

    stick = pygame.joystick.Joystick(0)
    stick.init()
    print(f"Joystick: {stick.get_name()}")
    print(f"# Axes: {stick.get_numaxes()}")

    max_id = max(discovered)
    joint_positions = [0.0] * (max_id + 1)

    # Shoulder => node1,2
    shoulder_ctrl = None
    if (1 in discovered) and (2 in discovered):
        shoulder_ctrl = ShoulderController(bus, [1,2])
        print("[INFO] ShoulderController for node1,node2 created.")

    # Gripper => node5,6
    gripper_ctrl = None
    if (5 in discovered) and (6 in discovered):
        gripper_ctrl = GripperController(bus, [5,6])
        print("[INFO] GripperController for node5,node6 created.")

    metrics_text = urwid.Text("Metrics...", align = 'left')
    joystick_text = urwid.Text("", align = 'left')
    box_metrics = urwid.LineBox(metrics_text, title = "ODrive Metrics")
    box_joy     = urwid.LineBox(joystick_text, title = "Controller Inputs")

    pile = urwid.Pile([box_metrics, box_joy])
    foot = urwid.Text("Press ESC to exit", align = 'center')
    frame = urwid.Frame(pile, footer = foot)

    loop = urwid.MainLoop(
        frame,
        palette = [('reversed','standout','')],
        unhandled_input = lambda k: handle_input(k, loop, discovered, bus, joint_positions)
    )

    ui_thread = threading.Thread(
        target = update_ui_thread,
        args = (bus, discovered, endpoints, metrics_text, joystick_text, loop),
        daemon = True
    )
    ui_thread.start()

    joy_thread = threading.Thread(
        target = joystick_thread_func,
        args = (bus, discovered, joint_positions, shoulder_ctrl, gripper_ctrl),
        daemon = True
    )
    joy_thread.start()

    try:
        loop.run()
    except KeyboardInterrupt:
        pass
    finally:
        print("[INFO] Main loop ended => stopping threads.")
        stop_event.set()
        ui_thread.join()
        joy_thread.join()
        print("[INFO] Threads joined => final shutdown.")
        clean_shutdown(discovered, bus, joint_positions)
        pygame.quit()


if __name__ == "__main__":
    main()