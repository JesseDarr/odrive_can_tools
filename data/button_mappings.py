DEAD_MAN_BUTTON_INDEX = 4     # LB
MODE_TOGGLE_BUTTON_INDEX = 5  # RB

ODRIVE_MAPPING = [
    {
        'node_index': 0,
        'joystick_axis': 0,  # Left Stick X
        'min_position': -4.8,
        'max_position': 4.8,
        'axis_name': 'Axis 0'
    },
    {
        'node_index': 1,
        'joystick_axis': 1,  # Left Stick Y
        'axis_name': 'Shoulder'
    },
    {
        'node_index': 2,
        'joystick_axis': 1,  # Also Left Stick Y (shared)
        'axis_name': 'Shoulder'
    },
    {
        'node_index': 3,
        'joystick_axis': 2,  # Right Stick X
        'min_position': -6.0,
        'max_position': 0.0,
        'axis_name': 'Axis 2',
        'invert': True
    },
    {
        'node_index': 4,
        'joystick_axis': 3,  # Right Stick Y
        'min_position': -4.8,
        'max_position': 4.8,
        'axis_name': 'Axis 3'
    },
    # node5, node6 => forearm; no joystick_axis here (we'll use the same left stick in code)
    {
        'node_index': 5,
        'axis_name': 'Forearm Bend'
    },
    {
        'node_index': 6,
        'axis_name': 'Forearm Rotate'
    },
]

SHOULDER = {
    'min': 0.0,
    'max': 5.1,
    'invert': True
}

FOREARM_UNISON = {
    'min': -25.0,
    'max': 25.0,
    'invert': False
}

FOREARM_DIFF = {
    'min': -25.0,
    'max': 25.0,
    'invert': False
}