import serial
import threading
import time
from datetime import datetime

from config import config as cfg

printer = None
serial_lock = threading.Lock()

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

    with serial_lock:
        # Send string to printer
        ser.write((gcode_string + '\n').encode())
        ser.flush()
        # Wait until printer accepts command
        lines = []
        while True:
            line = ser.readline().decode(errors='ignore').strip()
            lines.append(line)
            print(line)
            if line.lower() == 'ok':
                break
    return lines

def home(): run_gcode("G28")        # G-code to home; automatically waits until completion
def abs_pos(): run_gcode("G90")     # G-code to convert to absolute positioning mode
def rel_pos(): run_gcode("G91")     # G-code to convert to relative positioning mode
def get_pos(): return position_parser(run_gcode("M114"))      # G-code to return current position
def wait(): run_gcode("M400")       # G-code to wait until previous movement command completes
def show_stats(): print(run_gcode("M211"), run_gcode("M203"), run_gcode("M503"))

def position_parser(lines):
    X = 0
    Y = 1
    Z = 2
    position = lines[0].strip().split()
    position_dict = {
        "X": float(position[X].split(":")[1]),
        "Y": float(position[Y].split(":")[1]),
        "Z": float(position[Z].split(":")[1]),
    }
    return position_dict

