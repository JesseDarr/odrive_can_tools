# ODrive Tools

## Overview
These tools provide functionality for interacting with ODrive devices via a CAN bus, including device discovery, configuration, and demonstration actions such as setting positions or running predefined movements.

## Setup
- Requires Python 3.6 or newer.
- Dependencies: `python-can`. Install with `pip install python-can`.

## Tools and Scripts
- **calibrate.py**: Runs ODrive calibration sequence on each detected ODrive, one at a time.
- **clear_errors.py**: Clears all errors on detected ODrive devices.
- **setup.py**: Configures ODrive devices based on settings specified in `config.py`.
- **test_console.py**: Slider tUI, controls position for all ODrvies.

## Project Structure
```plaintext
tools/
├── README.md           
├── calibrate.py            - Calibrates ODrives
├── clear_errors.py         - Clears ODrive errors
├── console.py              - TUI test console to control motors
├── convert_id.py           - Changes ODrive node ids
├── gamecontroller.py       - Game controller console to control motors
├── setup.py                - Applies config.py values to all ODrives
├── velocity.py             - Very dengerous, do not use!!! only use to lube joint 0
├── data
│   ├── config.py           - Configuration settings for ODrive devices
│   └── flat_endpoints.json - Detailed list of ODrive firmware endpoints
└── src
    ├── can_utils.py        - Utility functions for CAN communication
    ├── configure.py        - Applies configurations to ODrive devices
    ├── control.py          - Interfaces for control actions on ODrive devices
    └── metrics.py          - Polls a variety of ODrive metrics    
```

## Configuration
- **config.py**: Contains user-defined settings for ODrive devices, such as motor parameters and control modes.
- Ensure this file is properly edited to match your hardware setup before running `setup.py`.

## Usage
1. **Configuring ODrives**: Run `python setup.py` to apply settings from `config.py` to connected ODrive devices.
2. **Clearing Errors**: Execute `python clear_errors.py` to clear any errors from ODrive devices, ensuring they are ready for operation.
3. **Demonstration Scripts**: Run `python test_console.py` to demonstrate various capabilities of the ODrive motors and display live metrics.

## Error Handling
Scripts are equipped with basic error handling for common issues such as missing configuration keys or communication failures, ensuring smooth operation during setup and demonstrations.