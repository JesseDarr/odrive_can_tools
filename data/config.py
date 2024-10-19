config = {
    "8308": {
        "settings": [
            {"path": "axis0.current_state",                             "value": 1},

            # DC bus settings
            {"path": "config.dc_bus_overvoltage_trip_level",            "value": 50}, 
            {"path": "config.dc_bus_undervoltage_trip_level",           "value": 20}, 
            {"path": "config.dc_max_positive_current",                  "value": 30},  
            {"path": "config.brake_resistor0.enable",                   "value": True},  
            {"path": "config.brake_resistor0.resistance",               "value": 2},  

            # Motor settings
            {"path": "axis0.config.motor.motor_type",                   "value": 0},  
            {"path": "axis0.config.motor.pole_pairs",                   "value": 20},  
            {"path": "axis0.config.motor.torque_constant",              "value": 0.92}, 
            {"path": "axis0.config.motor.current_soft_max",             "value": 25},  
            {"path": "axis0.config.motor.calibration_current",          "value": 18},  
            {"path": "axis0.config.motor.resistance_calib_max_voltage", "value": 5},  
            {"path": "axis0.config.calibration_lockin.current",         "value": 18},  
            {"path": "axis0.config.calib_range",                        "value": 0.02},

            # Control bandwidths
            {"path": "axis0.config.encoder_bandwidth",                  "value": 1000},
            {"path": "axis0.config.motor.current_control_bandwidth",    "value": 1000},

            # Controller settings
            {"path": "axis0.controller.config.input_mode",              "value": 5},    # 0 = inactive, 1 = passthrough, 2 = vel_ramp, 3 = pos_filter, 5 = trap_traj
            {"path": "axis0.controller.config.control_mode",            "value": 3},    # 0 = voltage, 1 = torque, 2 = velocity, 3 = position
            {"path": "axis0.controller.config.input_filter_bandwidth",  "value": 20},  
            {"path": "axis0.controller.config.vel_limit",               "value": 20},  
            {"path": "axis0.controller.config.vel_limit_tolerance",     "value": 1.8},

            # CAN settings
            {"path": "can.config.baud_rate",                            "value": 1000000},
            {"path": "axis0.config.can.heartbeat_msg_rate_ms",          "value": 100},
            {"path": "axis0.config.can.encoder_msg_rate_ms",            "value": 10}, 
            {"path": "axis0.config.can.iq_msg_rate_ms",                 "value": 10}, 
            {"path": "axis0.config.can.torques_msg_rate_ms",            "value": 10}, 
            {"path": "axis0.config.can.error_msg_rate_ms",              "value": 10},
            {"path": "axis0.config.can.bus_voltage_msg_rate_ms",        "value": 10},

            # Gains and limits
            {"path": "axis0.controller.config.pos_gain",                "value": 20},   # proportional gain # stiffness
            {"path": "axis0.controller.config.vel_gain",                "value": 0.14}, # derivative gain   # dampen overshoot
            {"path": "axis0.controller.config.vel_integrator_gain",     "value": 0.7},  # integral gain     # adjust steady-state error
            {"path": "axis0.trap_traj.config.vel_limit",                "value": 6},  
            {"path": "axis0.trap_traj.config.accel_limit",              "value": 20},  
            {"path": "axis0.trap_traj.config.decel_limit",              "value": 20}, 
            {"path": "axis0.controller.config.inertia",                 "value": 0}     # moment of inertia # try 0.33 to start
        ]
    },

    "GB36": {
        "settings": [
            {"path": "axis0.current_state",                             "value": 1},

            # DC bus settings
            {"path": "config.dc_bus_overvoltage_trip_level",            "value": 50}, 
            {"path": "config.dc_bus_undervoltage_trip_level",           "value": 20}, 
            {"path": "config.dc_max_positive_current",                  "value": 3},  
            {"path": "config.brake_resistor0.enable",                   "value": True},  
            {"path": "config.brake_resistor0.resistance",               "value": 2},  

            # Motor settings
            {"path": "axis0.config.motor.motor_type",                   "value": 2},
            {"path": "axis0.config.motor.phase_resistance",             "value": 16.4},
            {"path": "axis0.config.motor.pole_pairs",                   "value": 7},  
            {"path": "axis0.config.motor.torque_constant",              "value": 0.276}, 
            {"path": "axis0.config.motor.current_soft_max",             "value": 3},  
            {"path": "axis0.config.motor.calibration_current",          "value": 1.5},  
            {"path": "axis0.config.motor.resistance_calib_max_voltage", "value": 12},  
            {"path": "axis0.config.calibration_lockin.current",         "value": 1},  
            {"path": "axis0.config.calib_range",                        "value": 0.02},
            
            # Control bandwidths
            {"path": "axis0.config.encoder_bandwidth",                  "value": 1000},
            {"path": "axis0.config.motor.current_control_bandwidth",    "value": 1000},
            
            # Controller settings
            {"path": "axis0.controller.config.input_mode",              "value": 5},
            {"path": "axis0.controller.config.control_mode",            "value": 3},  
            {"path": "axis0.controller.config.input_filter_bandwidth",  "value": 20},  
            {"path": "axis0.controller.config.vel_limit",               "value": 12},  
            {"path": "axis0.controller.config.vel_limit_tolerance",     "value": 1.35},  
            
            # CAN settings
            {"path": "can.config.baud_rate",                            "value": 1000000},
            {"path": "axis0.config.can.heartbeat_msg_rate_ms",          "value": 100},
            {"path": "axis0.config.can.encoder_msg_rate_ms",            "value": 10}, 
            {"path": "axis0.config.can.iq_msg_rate_ms",                 "value": 10}, 
            {"path": "axis0.config.can.torques_msg_rate_ms",            "value": 10}, 
            {"path": "axis0.config.can.error_msg_rate_ms",              "value": 10},
            {"path": "axis0.config.can.bus_voltage_msg_rate_ms",        "value": 10},
            
            # Gains and limits
            {"path": "axis0.controller.config.pos_gain",                "value": 50},  
            {"path": "axis0.controller.config.vel_gain",                "value": 0.04},
            {"path": "axis0.controller.config.vel_integrator_gain",     "value": 0.004}, 
            {"path": "axis0.trap_traj.config.vel_limit",                "value": 6},  
            {"path": "axis0.trap_traj.config.accel_limit",              "value": 20},  
            {"path": "axis0.trap_traj.config.decel_limit",              "value": 20}, 
            {"path": "axis0.controller.config.inertia",                 "value": 0}
        ]
    }
}
