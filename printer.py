import serial
import time
from datetime import datetime

from config import config as cfg

printer = None

# Get printer serial without recreating serial connection
def get_printer():
    global printer
    if printer is None:
        try:
            printer = serial.Serial(cfg.device_path, baudrate=cfg.baudrate, timeout=cfg.timeout_time)
            print("Establishing Connection")
            time.sleep(2)

            printer.write(b'M115\n')
            while True:
                line = printer.readline().decode(errors='ignore').strip()
                if line.lower() == 'ok':
                    break
            print("Printer Connected")
            return printer
        except serial.SerialException as e:
            print(f"Failed to Connect: {e}")
            return None
    else:
        return printer

def close_printer():
    global printer
    if printer and printer.is_open:
        printer.close()
        printer = None
        print("Printer Closed")

def run_gcode(gcode_string):
    # Grab printer as ser
    ser = get_printer()
    # Send string to printer
    ser.write((gcode_string + '\n').encode())
    # Wait until printer accepts command
    while True:
        line = ser.readline().decode(errors='ignore').strip()
        if line.lower() == 'ok':
            break

def home(): run_gcode("G28")        # G-code to home; automatically waits until completion
def abs_pos(): run_gcode("G90")     # G-code to convert to absolute positioning mode
def rel_pos(): run_gcode("G91")     # G-code to convert to relative positioning mode
def wait(): run_gcode("M400")       # G-code to wait until previous movement command completes
