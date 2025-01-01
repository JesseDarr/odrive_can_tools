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

# ------------------------------
# 1) Button and axis definitions
# ------------------------------
DEAD_MAN_BUTTON_INDEX = 4  # LB
MODE_TOGGLE_BUTTON_INDEX = 5  # RB

AXIS_LEFT_X  = 0
AXIS_LEFT_Y  = 1
AXIS_RIGHT_X = 3
AXIS_RIGHT_Y = 4

DEAD_ZONE        = 0.25
VELOCITY_SCALING = 3.0
UPDATE_RATE      = 30.0

# ------------------------------
# 2) Joint clamp definitions
#    Node0 => Joint0
#    Node(1,2) => Joint1 (shoulder)
#    Node3 => Joint2
#    Node4 => Joint3
#    Node(5,6) => Forearm
# ------------------------------
JOINT0_MIN, JOINT0_MAX = -4.8, 4.8  # node0
JOINT1_MIN, JOINT1_MAX =  -5,    0  # node1,2 (shoulder), if needed
JOINT2_MIN, JOINT2_MAX =  -5,    5  # node3
JOINT3_MIN, JOINT3_MAX =  -6,    0  # node4

FOREARM_UNISON_MIN, FOREARM_UNISON_MAX = -25, 25
FOREARM_DIFF_MIN,   FOREARM_DIFF_MAX   = -25, 25

stop_event = threading.Event()

# We'll store joystick states for UI
joystick_states = {
    "LB": False,
    "axes": {AXIS_LEFT_X:0.0, AXIS_LEFT_Y:0.0, AXIS_RIGHT_X:0.0, AXIS_RIGHT_Y:0.0}
}

# ------------------------------
# 3) Helper functions
# ------------------------------
def apply_dead_zone(value):
    return 0.0 if abs(value) < DEAD_ZONE else value

def signal_handler(sig, frame):
    raise KeyboardInterrupt

def handle_input(key, loop, node_ids, bus, joint_positions):
    if key == 'esc':
        stop_event.set()
        raise urwid.ExitMainLoop()

def clean_shutdown(node_ids, bus, joint_positions):
    print("\nExiting... setting discovered ODrives to pos=0 => IDLE => shutdown.")
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

# ------------------------------
# 4) Shoulder & Forearm classes
# ------------------------------
class ShoulderController:
    """
    Node(1,2) => a single shoulder joint with two motors facing opposite directions.
    We track 'value' => motorA=+value, motorB=-value.
    We'll clamp if needed in code before we call apply().
    """
    def __init__(self, bus, node_ids):
        self.bus       = bus
        self.node_ids  = node_ids  # [1,2]
        self.value     = 0.0

    def apply(self):
        nA, nB = self.node_ids
        # If you want to clamp more strictly, do it here or in the thread
        motorA = self.value
        motorB = -self.value
        move_odrive_to_position(self.bus, nA, motorA)
        move_odrive_to_position(self.bus, nB, motorB)

class ForearmController:
    """
    Node(5,6) => forearm unison/diff:
      motorA = unison + diff
      motorB = unison - diff
    We'll clamp unison_val & diff_val with FOREARM_*
    """
    def __init__(self, bus, node_ids):
        self.bus       = bus
        self.node_ids  = node_ids  # [5,6]
        self.unison_val = 0.0
        self.diff_val   = 0.0

    def apply(self):
        # clamp
        if self.unison_val < FOREARM_UNISON_MIN: self.unison_val = FOREARM_UNISON_MIN
        if self.unison_val > FOREARM_UNISON_MAX: self.unison_val = FOREARM_UNISON_MAX
        if self.diff_val   < FOREARM_DIFF_MIN:   self.diff_val   = FOREARM_DIFF_MIN
        if self.diff_val   > FOREARM_DIFF_MAX:   self.diff_val   = FOREARM_DIFF_MAX

        nA, nB = self.node_ids
        motorA = self.unison_val + self.diff_val
        motorB = self.unison_val - self.diff_val
        move_odrive_to_position(self.bus, nA, motorA)
        move_odrive_to_position(self.bus, nB, motorB)

# ------------------------------
# 5) UI update thread
# ------------------------------
def update_ui_thread(bus, node_ids, endpoints, metrics_text, joystick_text, loop):
    # Build widths
    col_widths = {}
    for metric in METRIC_ENDPOINTS:
        col_widths[metric] = max(len(metric),4)+3

    node_col_w = 6
    header = f"{'Node':<{node_col_w}}" + "".join(
        f"{m:<{col_widths[m]}}" for m in METRIC_ENDPOINTS
    )

    axis_names = ["LeftX","LeftY","RightX","RightY"]
    axis_col_w = max(len(x) for x in axis_names) + 3
    joy_header_line = "LB".ljust(8) + "".join(x.ljust(axis_col_w) for x in axis_names)

    while not stop_event.is_set():
        # ODrive metrics
        lines = [header]
        for nid in node_ids:
            data = get_metrics(bus, nid, endpoints)
            row = f"{nid:<{node_col_w}}"
            for metric in METRIC_ENDPOINTS:
                val = data.get(metric, None)
                if isinstance(val, (int,float)):
                    sign_space= ' ' if val>=0 else ''
                    row+= f"{sign_space}{val:.2f}".ljust(col_widths[metric])
                else:
                    row+= f"{'None':<{col_widths[metric]}}"
            lines.append(row)
        metrics_text.set_text("\n".join(lines))

        # Joystick line
        lb_str = "Pressed" if joystick_states["LB"] else "NotPress"
        joy_line = lb_str.ljust(8)
        for idx in (AXIS_LEFT_X, AXIS_LEFT_Y, AXIS_RIGHT_X, AXIS_RIGHT_Y):
            v = joystick_states["axes"].get(idx, 0.0)
            joy_line += f"{v:>6.2f}".ljust(axis_col_w)

        joystick_text.set_text(joy_header_line + "\n" + joy_line)

        time.sleep(0.1)
        try:
            loop.draw_screen()
        except (urwid.ExitMainLoop, RuntimeError):
            break

# ------------------------------
# 6) Main joystick logic thread
# ------------------------------
def joystick_thread_func(bus, node_ids, joint_positions,
                         shoulder_ctrl, forearm_ctrl,
                         update_rate=UPDATE_RATE):
    clock = pygame.time.Clock()
    js= pygame.joystick.Joystick(0)
    js.init()

    while not stop_event.is_set():
        dt= clock.tick(update_rate)/1000.0
        pygame.event.pump()

        lb= js.get_button(DEAD_MAN_BUTTON_INDEX)
        rb= js.get_button(MODE_TOGGLE_BUTTON_INDEX)
        joystick_states["LB"] = bool(lb)

        # read left stick
        lx= apply_dead_zone(js.get_axis(AXIS_LEFT_X))
        ly= apply_dead_zone(js.get_axis(AXIS_LEFT_Y))
        # read right stick
        rx= apply_dead_zone(js.get_axis(AXIS_RIGHT_X))
        ry= apply_dead_zone(js.get_axis(AXIS_RIGHT_Y))

        # store for UI
        joystick_states["axes"][AXIS_LEFT_X]  = lx
        joystick_states["axes"][AXIS_LEFT_Y]  = ly
        joystick_states["axes"][AXIS_RIGHT_X] = rx
        joystick_states["axes"][AXIS_RIGHT_Y] = ry

        # Movement only if LB pressed
        if lb:
            forearm_mode = (rb==1)

            # Joint 2 => Node 3 => Right Stick X
            if 3 in node_ids:
                joint_positions[2]+= rx*VELOCITY_SCALING*dt
                if joint_positions[2]<JOINT2_MIN: joint_positions[2]=JOINT2_MIN
                if joint_positions[2]>JOINT2_MAX: joint_positions[2]=JOINT2_MAX
                move_odrive_to_position(bus, 3, joint_positions[2])

            # Joint 3 => Node 4 => Right Stick Y
            if 4 in node_ids:
                joint_positions[3] -= ry*VELOCITY_SCALING*dt
                if joint_positions[3]<JOINT3_MIN: joint_positions[3]=JOINT3_MIN
                if joint_positions[3]>JOINT3_MAX: joint_positions[3]=JOINT3_MAX
                move_odrive_to_position(bus, 4, joint_positions[3])

            if not forearm_mode:
                # => left stick controls Joint0 & Joint1
                # Joint0 => Node0 => leftX => joint_positions[0]
                if 0 in node_ids:
                    joint_positions[0]+= lx*VELOCITY_SCALING*dt
                    if joint_positions[0]<JOINT0_MIN: joint_positions[0]=JOINT0_MIN
                    if joint_positions[0]>JOINT0_MAX: joint_positions[0]=JOINT0_MAX
                    move_odrive_to_position(bus, 0, joint_positions[0])

                # Joint1 => Node(1,2) => leftY => Shoulder
                if shoulder_ctrl and (1 in node_ids) and (2 in node_ids):
                    # We'll clamp if needed (like JOINT1_MIN, JOINT1_MAX)
                    # but we do so by adjusting 'shoulder_ctrl.value'
                    new_val = shoulder_ctrl.value + ly*VELOCITY_SCALING*dt
                    if new_val<JOINT1_MIN: new_val=JOINT1_MIN
                    if new_val>JOINT1_MAX: new_val=JOINT1_MAX
                    shoulder_ctrl.value= new_val
                    shoulder_ctrl.apply()
            else:
                # => left stick controls Forearm (diff=lx, unison=ly)
                if forearm_ctrl and (5 in node_ids) and (6 in node_ids):
                    forearm_ctrl.diff_val   += (lx*VELOCITY_SCALING*dt)
                    forearm_ctrl.unison_val += (ly*VELOCITY_SCALING*dt)
                    forearm_ctrl.apply()
        else:
            pass

        time.sleep(0.01)


# ------------------------------
# 7) Main function
# ------------------------------
def main():
    signal.signal(signal.SIGINT, signal_handler)

    bus = can.interface.Bus("can0", bustype="socketcan")
    discovered= list(discover_node_ids(bus))
    endpoints= load_endpoints()

    if not discovered:
        print("[ERROR] No ODrives found on the CAN bus.")
        return

    discovered.sort()
    print(f"Discovered ODrive Node IDs: {discovered}")

    # Set to closed-loop
    for nid in discovered:
        if not set_closed_loop_control(bus, nid):
            print(f"[ERROR] Could not set node {nid} to CLOSED_LOOP_CONTROL.")
            bus.shutdown()
            return

    # Init pygame
    pygame.init()
    pygame.joystick.init()
    if pygame.joystick.get_count()==0:
        print("[ERROR] No joystick found.")
        pygame.quit()
        return

    stick= pygame.joystick.Joystick(0)
    stick.init()
    print(f"Joystick: {stick.get_name()}")
    print(f"# Axes: {stick.get_numaxes()}")

    max_nid= max(discovered)
    # We'll keep joint_positions for node0 => index0 => joint0, etc
    # node3 => index3 => joint2, node4 => index4 => joint3, etc
    joint_positions= [0.0]*(max_nid+1)

    # Build Shoulder => node1,2
    shoulder_ctrl= None
    if (1 in discovered) and (2 in discovered):
        shoulder_ctrl= ShoulderController(bus, [1,2])
        print("[INFO] ShoulderController for node1,node2 created.")

    # Forearm => node5,6
    forearm_ctrl= None
    if (5 in discovered) and (6 in discovered):
        forearm_ctrl= ForearmController(bus, [5,6])
        print("[INFO] ForearmController for node5,node6 created.")

    # Build text UI
    metrics_text= urwid.Text("Metrics...",align='left')
    joystick_text= urwid.Text("",align='left')
    box_metrics= urwid.LineBox(metrics_text, title="ODrive Metrics")
    box_joy= urwid.LineBox(joystick_text, title="Controller Inputs")

    pile= urwid.Pile([box_metrics, box_joy])
    foot= urwid.Text("Press ESC to exit", align='center')
    frame= urwid.Frame(pile, footer=foot)

    loop= urwid.MainLoop(
        frame,
        palette=[('reversed','standout','')],
        unhandled_input=lambda k: handle_input(k, loop, discovered, bus, joint_positions)
    )

    ui_thread= threading.Thread(
        target=update_ui_thread,
        args=(bus, discovered, endpoints, metrics_text, joystick_text, loop),
        daemon=True
    )
    ui_thread.start()

    joy_thread= threading.Thread(
        target=joystick_thread_func,
        args=(bus, discovered, joint_positions, shoulder_ctrl, forearm_ctrl),
        daemon=True
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


if __name__=="__main__":
    main()