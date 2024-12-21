DEAD_MAN_BUTTON_INDEX = 4     # LB
MODE_TOGGLE_BUTTON_INDEX = 5  # RB

ODRIVE_MAPPING = [
    {
        'node_index': 0,       
        'joystick_axis': 0,    # Left Stick X
        'start_position': 0.0,
        'min_position': -4.8,
        'max_position': 4.8,
        'axis_name': 'Axis 0'
    },
    {
        'node_index': 1,
        'joystick_axis': 1,    # Left Stick Y
        'start_position': 0.0,
        'min_position': 0.0,
        'max_position': 5.5,
        'axis_name': 'Axis 1',
        'invert': True
    },
    {
        'node_index': 2,
        'joystick_axis': 3,    # Right Stick X
        'start_position': 0.0,
        'min_position': -4.8,
        'max_position': 4.8,
        'axis_name': 'Axis 2'
    },
    {
        'node_index': 3,
        'joystick_axis': 4,    # Right Stick Y
        'start_position': 0.0,
        'min_position': -6.0,
        'max_position': 0,
        'axis_name': 'Axis 3',
        'invert': True
    },
    {
        'node_index': 4,
        'joystick_axis': 2,    # For forearm mode
        'start_position': 0.0,
        'axis_name': 'Axis 4'
    },
    {
        'node_index': 5,
        'joystick_axis': 5,    # For forearm mode
        'start_position': 0.0,
        'axis_name': 'Axis 5'
    },
]

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