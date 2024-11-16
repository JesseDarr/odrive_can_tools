# ODrive Tools

## Overview
These tools provide functionality for interacting with ODrive devices via a CAN bus, including device discovery, configuration, and demonstration actions such as setting positions or running predefined movements.

## Setup
- Requires Python 3.6 or newer.
- Dependencies: `python-can`. Install with `pip install python-can`.

## Tools and Scripts
- **clear_all_errors.py**: Clears all errors on detected ODrive devices.
- **setup_odrives.py**: Configures ODrive devices based on settings specified in `config.json`.
- **slider_explorer.py**: Slider tUI, controls position for all ODrvies.

## Project Structure
```plaintext
tools/
├── README.md
├── clear_all_errors.py
├── setup_odrives.py
├── slider_explorer.py
├── data
│   ├── config.json             - Configuration settings for ODrive devices.
│   └── flat_endpoints.json     - Detailed list of ODrive firmware endpoints.
└── src
    ├── can_utils.py            - Utility functions for CAN communication.
    ├── odrive_configurator.py  - Applies configurations to ODrive devices.
    └── odrive_control.py       - Interfaces for control actions on ODrive devices.
```

## Configuration
- **config.json**: Contains user-defined settings for ODrive devices, such as motor parameters and control modes.
- Ensure this file is properly edited to match your hardware setup before running `setup_odrives.py`.

## Usage
1. **Configuring ODrives**: Run `python setup_odrives.py` to apply settings from `config.json` to connected ODrive devices.
2. **Clearing Errors**: Execute `python clear_all_errors.py` to clear any errors from ODrive devices, ensuring they are ready for operation.
3. **Demonstration Scripts**: Use `do_the_wave.py`, `set_position.py`, and `slider_explorer.py` to demonstrate various capabilities of the ODrive motors.

## Error Handling
Scripts are equipped with basic error handling for common issues such as missing configuration keys or communication failures, ensuring smooth operation during setup and demonstrations.