#!/usr/bin/env python3
"""
Graphical User Interface based off the version created by Johnny Duong
Author: Darren Lee
TODO: add preview window

"""
from datetime import datetime
from picamera.array import PiRGBArray, PiBayerArray
from picamera import PiCamera
from Xlib.display import Display
import csv
import FreeSimpleGUI as sg
import cv2
import numpy as np
import os
import time
import threading
import random
import queue
import serial

# Import modules
from config import config as cfg
import printer as printer
import io_helper as ioh

# ===== GUI KEYS =====
class Keys:
    # ===== RUN CAPTURE TAB (1) =====
    # ----- Capture Settings -----
    INPUT_CSV = "-CSV_INPUT-"
    NUM_COLS = "-COL-"
    NUM_ROWS = "-ROW-"
    OUTPUT_DIR = "-OUTPUT_DIR_INPUT-"
    OUTPUT_PREFIX = "-OUTPUT_PREFIX-"
    OUTPUT_SUFFIX = "-OUTPUT_SUFFIX-"
    OUTPUT_PREVIEW = "-OUTPUT_PREVIEW-"
    # ----- Camera Settings -----
    OPEN_SECTION = "-OPEN_SECTION-"
    CAMERA_SECTION = "-CAMERA_SECTION-"
    PIC_WIDTH = "-PIC_WIDTH-"
    PIC_HEIGHT = "PIC_HEIGHT-"
    # Core
    ROTATION = "-ROTATION-"
    FRAMERATE = "-FRAMERATE-"
    ISO = "-ISO-"
    SHUTTER = "-SHUTTER-"
    SLEEP_MULT = "-SLEEP_MULT-"
    EXPOSURE_MODE = "-EXPOSURE_MODE-"
    AWB_MODE = "-AWB_MODE-"
    # Tuning
    BRIGHTNESS = "-BRIGHTNESS-"
    BRIGHTNESS_VAL = "-BRIGHTNESS_VAL-"
    SATURATION = "-SATURATION-"
    SATURATION_VAL = "-SATURATION_VAL-"
    CONTRAST = "-CONTRAST-"
    CONTRAST_VAL = "-CONTRAST_VAL-"
    SHARPNESS = "-SHARPNESS-"
    SHARPNESS_VAL = "-SHARPNESS_VAL-"
    RED_GAIN = "-AWB_GAINS1-"
    BLUE_GAIN = "-AWB_GAINS2-"

    # ----- Mode Selector -----
    PICTURE_MODE = "-PIC_MODE-"
    PREVIEW_MODE = "-PREV_MODE-"
    # ----- Output Manager -----
    VERBOSE_MODE = "-VERBOSE-"
    # ----- Capture Controller -----
    START_CAPTURE = "-START_CAPTURE-"
    STOP_CAPTURE = "-STOP_CAPTURE-"
    GO_HOME = "-HOME-"
    # ----- Output Element -----
    OUTPUT_WINDOW = "-OUTPUT-"

class Logger:
    def __init__(self, verbose=True, output_queue=None):
        self.verbose = verbose
        self.q = output_queue

    # Verbose mode logger
    def log(self, msg, level="INFO"):
        if self.verbose:
            self.q.put(f"[{level}] {msg}")
    
    def info(self, msg): self.log(msg, "INFO")
    def debug(self, msg): self.log(msg, "DEBUG")
    def warn(self, msg): self.log(msg, "WARNING")
    def error(self, msg): self.log(msg, "ERROR")

    # Regular print message
    def say(self, msg): self.q.put(msg)

def run_home(event, values, log, thread_done):
    """
    """
    log.say("Moving Extruder and Build Plate to Origin/Home")

    printer.home()
    
    thread_done.set()

def run_capture(event, values, log, thread_done, thread_stop, preview_win_id):
    """
    """
    # Load Camera
    try:
        camera.close()
    except:
        pass
    camera = PiCamera()     # Define camera
    log.info("Turning on camera")

    # Load Camera Settings
    # Core
    camera.resolution = (int(values[Keys.PIC_WIDTH]), int(values[Keys.PIC_HEIGHT]))
    camera.rotation = int(cfg.rotation)
    camera.framerate = float(values[Keys.FRAMERATE])
    camera.iso = int(values[Keys.ISO])
    camera.shutter_speed = int(values[Keys.SHUTTER])
    camera.exposure_mode = str(values[Keys.EXPOSURE_MODE])
    camera.awb_mode = str(values[Keys.AWB_MODE])
    # Tuning
    camera.brightness = int(values[Keys.BRIGHTNESS])
    camera.contrast = int(values[Keys.CONTRAST])
    camera.sharpness = int(values[Keys.SHARPNESS])
    camera.saturation = int(values[Keys.SATURATION])
    camera.awb_gains = (float(values[Keys.RED_GAIN]), float(values[Keys.BLUE_GAIN]))
    log.info("Settings loaded")

    ser = printer.get_printer()

    # Option Booleans
    preview_mode = bool(values[Keys.PREVIEW_MODE])
    verbose_mode = bool(values[Keys.VERBOSE_MODE])

    # Get CSV Filename
    csv_file_path = values[Keys.INPUT_CSV]
    location_list = ioh.load_gcode_from_csv(csv_file=csv_file_path)

    # Intiializes to clear the plate
    log.say("Initializing...")
    printer.rel_pos()
    log.info("Clearing: G0Z+40.00")
    printer.run_gcode("G0Z+40.00")
    # Wait until motion is DONE
    printer.wait()
    printer.abs_pos()
    log.info(f"Moving to start: {location_list[0]}")
    printer.run_gcode(location_list[0])
    # Wait until motion is DONE
    printer.wait()

    # Start Message
    log.say("==================================================")
    log.say("Flycam Capture")
    log.say(f"Rows: {cfg.num_rows}")
    log.say(f"Columns: {cfg.num_cols}")
    log.say(f"Output path: {values[Keys.OUTPUT_DIR]}")
    log.say(f"Mode: {'Preview' if values[Keys.PREVIEW_MODE] else 'Picture'}")
    log.say("==================================================")
    log.say("")
    log.say("Process Starting!")

    # Cycles through each well in a snakelike pattern
    # Checks for even rows (pos) to determine well number
    even_row_flag = False
    rows = int(cfg.num_rows)
    cols = int(cfg.num_cols)
    well_count = rows * cols
    for cycle, location in zip(range(1,rows*cols+1), location_list):
        if thread_stop.is_set():
            camera.close()
            thread_done.set()
            return
        # Determine well number
        if even_row_flag is True:
            well_number = ((cycle-1)//cols)*cols + (cols-((cycle-1)%cols))
        else:
            well_number = cycle
        
        # Move to location
        printer.run_gcode(location)
        log.info(f'Cycle {cycle}/{well_count}: Going to Well Number {"%02d" % well_number}')
        printer.wait()
        time.sleep(float(cfg.move_sleep_time))

        # Take Picture
        if preview_mode is False:
            log.info(f"Starting capture cycle")           
            photo_file_path = ioh.get_photo_path(values[Keys.OUTPUT_DIR], values[Keys.OUTPUT_PREFIX], values[Keys.OUTPUT_SUFFIX], "%02d" % well_number)
            os.makedirs(os.path.dirname(photo_file_path), exist_ok=True)
            camera.capture(photo_file_path)
            capture_sleep_time = (camera.shutter_speed / 1_000_000 * float(cfg.sleep_multiplier)) + float(cfg.sleep_addition)
            log.debug(f"Sleeping for {capture_sleep_time} seconds")
            time.sleep(capture_sleep_time)
            log.say(f"[INFO] Captured image {cycle}/{well_count}")
            log.info(f"Saved image as {photo_file_path}.jpg")
        else:
            log.info(f"Starting capture cycle")           
            photo_file_path = ioh.get_photo_path(values[Keys.OUTPUT_DIR], values[Keys.OUTPUT_PREFIX], values[Keys.OUTPUT_SUFFIX], "%02d" % well_number)
            capture_sleep_time = (camera.shutter_speed / 1_000_000 * float(cfg.sleep_multiplier)) + float(cfg.sleep_addition)
            log.debug(f"Sleeping for {capture_sleep_time} seconds")
            time.sleep(capture_sleep_time)
            log.say(f"[INFO] No image captured (preview mode is ON)")
            log.info(f"Did not save image as {photo_file_path}.jpg")
        
        # Flips row flag every 8 columns
        if cycle % cols == 0:
            even_row_flag = not even_row_flag

    log.say("Process Complete!")
    log.say("")
    log.say("==================================================")
    if preview_mode is False:
        log.say(f"{well_count} Images Captured")
        log.say(f"Output path: {values[Keys.OUTPUT_DIR]}")
    else:
        log.say("No Images Captured, Preview mode is ON")
    log.say("==================================================")

    # Close camera
    camera.close()
    print("Camera Closed")
    # Send Flag to close thread
    thread_done.set()

    return

def main():

    print("Opening Flycam GUI...")
    
    # Try to close any unended processes from previous crashes/errors
    # Safely initializes a single camera instance
    try:
        camera.close()
    except:
        pass
    camera = PiCamera()     # Define camera
    print("Camera Opened")
    # Set Preview Settings
    camera.resolution = (cfg.preview.width, cfg.preview.height)
    camera.framerate = cfg.framerate
    camera.rotation = cfg.rotation
    
    # Gain Adjustment
    pre_value = camera.digital_gain
    cur_value = -1
    # for i in range(20):
    # Wait for digital gain values to settle, then break out of loop
    while pre_value != cur_value:
        pre_value = cur_value
        # pre gets cur 
        # cur get new
        
        cur_value = camera.digital_gain
        #if pre_value != cur_value:
        #    pre_value = cur_value
        
        print(f"digital_gain: {cur_value}")
        time.sleep(0.5)

    # ===== Printer Startup =====
    # Setup 3D Printer
    ser = printer.get_printer()

    print("Moving Extruder and Build Plate to Origin/Home")
    printer.home()
    print("Done!")
    print("Opening Window")

    # ===== GUI Window Layout =====
    sg.theme("LightBrown2")
    # sg.set_options(font=('Courier',12))
    # ----- Tab 1 (Run Capture) -----
    core_settings_col = [
        [sg.Push(), sg.Text("Core Settings"), sg.Push()],
        # [sg.Text("Rotation"), sg.Push(), sg.Input(cfg.rotation, size=(6,1), key=Keys.ROTATION)],
        [sg.Text("Resolution"), sg.Push(), sg.Input(cfg.picture.width, size=(6,1),key=Keys.PIC_WIDTH), sg.Text("x"), sg.Input(cfg.picture.height, size=(6,1), key=Keys.PIC_HEIGHT)],
        [sg.Text("Framerate"), sg.Push(), sg.Input(cfg.framerate, size=(6,1), key=Keys.FRAMERATE)],
        [sg.Text("ISO"), sg.Push(), sg.Input(cfg.iso, size=(6,1), key=Keys.ISO)],
        [sg.Text("Shutter Speed (μs)"), sg.Push(), sg.Input(cfg.shutter, size=(10,1), key=Keys.SHUTTER)],
        # [sg.Text("Sleep Multiplier"), sg.Push(), sg.Input(cfg.sleep_multiplier, size=(10,1), key=Keys.SLEEP_MULT)],
        [sg.Text("Exposure Mode"), sg.Push(), sg.Combo(['off',
            'auto',
            'nightpreview',
            'backlight',
            'spotlight',
            'sports',
            'snow',
            'beach',
            'verylong',
            'fixedfps',
            'antishake',
            'fireworks',
            ], default_value=cfg.exposure_mode, key=Keys.EXPOSURE_MODE, enable_events=True)],
        [sg.Text("AWB Mode"), sg.Push(), sg.Combo(['off',
            'auto',
            'sunlight',
            'cloudy',
            'shade',
            'tungsten',
            'fluorescent',
            'incandescent',
            'flash',
            'horizon',
            ], default_value=cfg.awb_mode, key=Keys.AWB_MODE, enable_events=True)],
    ]
    tuning_settings_col = [
        [sg.Push(), sg.Text("Tuning Settings"), sg.Push()],
        [sg.Text("Brightness"), sg.Push(), sg.Slider(range=(0,100), default_value=cfg.brightness, orientation='h', size=(20,15), key=Keys.BRIGHTNESS, enable_events=True, disable_number_display=True), sg.Input(cfg.brightness, key=Keys.BRIGHTNESS_VAL, size=(5,1), enable_events=True)],
        [sg.Text("Contrast"), sg.Push(), sg.Slider(range=(-100,100), default_value=cfg.contrast, orientation='h', size=(20,15), key=Keys.CONTRAST, enable_events=True, disable_number_display=True), sg.Input(cfg.contrast, key=Keys.CONTRAST_VAL, size=(5,1), enable_events=True)],
        [sg.Text("Sharpness"), sg.Push(), sg.Slider(range=(-100,100), default_value=cfg.sharpness, orientation='h', size=(20,15), key=Keys.SHARPNESS, enable_events=True, disable_number_display=True), sg.Input(cfg.sharpness, key=Keys.SHARPNESS_VAL, size=(5,1), enable_events=True)],
        [sg.Text("Saturation"), sg.Push(), sg.Slider(range=(-100,100), default_value=cfg.saturation, orientation='h', size=(20,15), key=Keys.SATURATION, enable_events=True, disable_number_display=True), sg.Input(cfg.saturation, key=Keys.SATURATION_VAL, size=(5,1), enable_events=True)],
        [sg.Text("AWB Gains (R/B)"), sg.Push(),
            sg.Input(cfg.red_gain, size=(5,1), key=Keys.RED_GAIN),
            sg.Input(cfg.blue_gain, size=(5,1), key=Keys.BLUE_GAIN)],
    ]
    tab_1_column_1_collapse_layout = sg.pin(sg.Column([[
        sg.Column(core_settings_col, vertical_alignment='top'),
        sg.VSeparator(),
        sg.Column(tuning_settings_col, vertical_alignment='top')
    ]], key=Keys.CAMERA_SECTION, visible=False))
    tab_1_column_1_layout = [
        [sg.Text("Auto Capture", font=(None, 14, 'bold'))],
        [sg.Text("Input CSV"), sg.Push(), sg.Input(size=(40, 1), default_text=f"{os.getcwd() if not cfg.input_csv else cfg.input_csv}/{'location_file_snake_path.csv' if not cfg.input_csv else ''}", key=Keys.INPUT_CSV), sg.FileBrowse()],
        [sg.Text("Output Folder"), sg.Push(), sg.Input(size=(40, 1), default_text=f"{os.getcwd() if not cfg.output_dir else cfg.output_dir}{'/well_photos' if not cfg.output_dir else ''}", enable_events=True, key=Keys.OUTPUT_DIR), sg.FolderBrowse()],
        [sg.Text("Output Prefix"), sg.Push(), sg.Input(size=(40, 1), default_text=cfg.output_prefix, enable_events=True, key=Keys.OUTPUT_PREFIX)],
        [sg.Text("Output Suffix"), sg.Push(), sg.Input(size=(40, 1), default_text=cfg.output_suffix, enable_events=True, key=Keys.OUTPUT_SUFFIX)],
        [sg.Push(), sg.Text(f"{os.getcwd() if not cfg.output_dir else cfg.output_dir}{'/well_photos' if not cfg.output_dir else ''}/{cfg.output_prefix}wellXX_YYYY-MM-DD_hhmmss{cfg.output_suffix}.jpg", text_color='darkolivegreen', key=Keys.OUTPUT_PREVIEW)],
        # [sg.Text("Well Plate Size "), sg.Input(default_text=cfg.num_cols, size=(3, 1), key=Keys.NUM_COLS), sg.Text("columns x "),
        # sg.Input(default_text=cfg.num_rows, size=(3, 1), key=Keys.NUM_ROWS), sg.Text("rows")],
        [sg.VPush()],
        [sg.Text("▶ Camera Settings", enable_events=True, key=Keys.OPEN_SECTION)],
        [tab_1_column_1_collapse_layout],
        [sg.Text("Select Capture Mode")],
        [sg.Radio("Preview", group_id="MODE_GROUP", default=cfg.preview_by_default, key=Keys.PREVIEW_MODE),
        sg.Radio("Picture", group_id="MODE_GROUP", default=cfg.picture_by_default, key=Keys.PICTURE_MODE)],
        [sg.Button("▶ Start Capture", button_color=(None, 'darkolivegreen'), key=Keys.START_CAPTURE, disabled=True),
        sg.Button("■ Stop Capture", button_color=(None, 'darkred'), key=Keys.STOP_CAPTURE, disabled=True),
        sg.Button("⌂ Home", button_color=(None, 'darkgoldenrod'), key=Keys.GO_HOME)]
    ]
    tab_1_column_2_layout = [
        # [sg.Output(size=(30, 12), key=Keys.OUTPUT_WINDOW, expand_y=True)],
        [sg.Text("Terminal Output")],
        [sg.Checkbox("Verbose", default=cfg.verbose_mode, key=Keys.VERBOSE_MODE)]
    ]
    tab_1_layout = [
        [sg.Column(tab_1_column_1_layout), sg.Column(tab_1_column_2_layout, expand_y=True)]
    ]
    # ----- Tab 2 (Manual Mode) -----
    tab_2_layout =[
        [sg.Text("To be implemented", text_color='red')]
        ]
    # ----- Define Window Layout -----
    layout = [ [sg.TabGroup([
        [sg.Tab("Auto Capture", tab_1_layout)],
        [sg.Tab("Manual Controller", tab_2_layout)]
        ])]
    ]
    # Create window
    window = sg.Window("Flycam GUI Rebuilt", layout)

    # ===== Preview Window =====
    # TODO: Preview Window Setup, 0 for dummy value
    preview_win_id = 0

    # ===== Initilize/Loop Setup =====
    # ----- Threading Steup -----
    # Initialize Empty thread object. Used with "Start Capture" and "Home"

    thread = threading.Thread()
    # Initialize threading event. Used to stop the thread
    thread_stop = threading.Event()
    thread_done = threading.Event()
    
    # ----- Flags and variables ----- 
    # Boolean flag to know if which thread is running
    is_running_capture = False
    is_running_home = False

    opened = False
    # ----- Logger setup -----
    output_queue = queue.Queue()
    log = Logger(verbose=True, output_queue=output_queue)

    # ===== GUI loop =====
    try:
        while True:
            event, values = window.read(timeout=10)

            # ----- Capture Controller Defaults -----
            # Enable/disable Capture Controller Buttons dependent on CSV field input
            if len(values[Keys.INPUT_CSV]) > 0 and not is_running_capture and not is_running_home:
                # Enable "Start Capture" button
                window[Keys.START_CAPTURE].update(disabled=False)

                # Disable "End Capture" button
                window[Keys.STOP_CAPTURE].update(disabled=True)
            else:
                # Disable "Start Capture" button
                window[Keys.START_CAPTURE].update(disabled=True)

            # ----- If/elif event chain -----
            # Close Window
            if event == sg.WIN_CLOSED:
                print("Closing Flycam GUI...")
                break
            elif event == Keys.OUTPUT_DIR or event == Keys.OUTPUT_PREFIX or event == Keys.OUTPUT_SUFFIX:
                window[Keys.OUTPUT_PREVIEW].update(f"{values[Keys.OUTPUT_DIR]}/{values[Keys.OUTPUT_PREFIX]}wellXX_YYYY-MM-DD_hhmmss{values[Keys.OUTPUT_SUFFIX]}.jpg")
            # Camera Settings Section
            elif event.startswith(Keys.OPEN_SECTION):
                opened = not opened
                window[Keys.OPEN_SECTION].update("▼ Camera Settings" if opened else "▶ Camera Settings")
                window[Keys.CAMERA_SECTION].update(visible=opened)
            # Update Slider and Text
            # Brightness
            elif event == Keys.BRIGHTNESS:
                val = int(values[Keys.BRIGHTNESS])
                window[Keys.BRIGHTNESS_VAL].update(val)
            elif event == Keys.BRIGHTNESS_VAL:
                val_str = values[Keys.BRIGHTNESS_VAL]
                try:
                    val = int(val_str)
                    if val < 0:
                        val = 0
                    elif val > 100:
                        val = 100
                    
                    if val != int(val_str):
                        window[Keys.BRIGHTNESS_VAL].update(str(val))

                    window[Keys.BRIGHTNESS].update(val)
                except ValueError:
                    pass
            
            elif event == Keys.CONTRAST:
                val = int(values[Keys.CONTRAST])
                window[Keys.CONTRAST_VAL].update(val)
            elif event == Keys.CONTRAST_VAL:
                val_str = values[Keys.CONTRAST_VAL]
                try:
                    val = int(val_str)
                    if val < -100:
                        val = -100
                    elif val > 100:
                        val = 100
                    
                    if val != int(val_str):
                        window[Keys.CONTRAST_VAL].update(str(val))

                    window[Keys.CONTRAST].update(val)
                except ValueError:
                    pass
            
            elif event == Keys.SHARPNESS:
                val = int(values[Keys.SHARPNESS])
                window[Keys.SHARPNESS_VAL].update(val)
            elif event == Keys.SHARPNESS_VAL:
                val_str = values[Keys.SHARPNESS_VAL]
                try:
                    val = int(val_str)
                    if val < -100:
                        val = -100
                    elif val > 100:
                        val = 100
                    
                    if val != int(val_str):
                        window[Keys.SHARPNESS_VAL].update(str(val))

                    window[Keys.SHARPNESS].update(val)
                except ValueError:
                    pass
            
            elif event == Keys.SATURATION:
                val = int(values[Keys.SATURATION])
                window[Keys.SATURATION_VAL].update(val)
            elif event == Keys.SATURATION_VAL:
                val_str = values[Keys.SATURATION_VAL]
                try:
                    val = int(val_str)
                    if val < -100:
                        val = -100
                    elif val > 100:
                        val = 100
                    
                    if val != int(val_str):
                        window[Keys.SATURATION_VAL].update(str(val))

                    window[Keys.SATURATION].update(val)
                except ValueError:
                    pass
                
            # Start Capture Button
            elif event == Keys.START_CAPTURE:
                print("Pressed START_CAPTURE")

                # Change capture cycle flag
                is_running_capture = True

                # Enable/disable Capture Controller Buttons
                # Disable "Start Capture" button
                window[Keys.START_CAPTURE].update(disabled=True)
                # Enable "End Capture" button
                window[Keys.STOP_CAPTURE].update(disabled=False)
                # Disable "Home" Button
                window[Keys.GO_HOME].update(disabled=True)

                # Close camera so thread can open its own camera
                camera.close()
                print("Camera Closed")

                # Start threaded capture
                thread = threading.Thread(target=run_capture, args=(event, values, log, thread_done, thread_stop, preview_win_id), daemon=True)
                thread.start()

            # Stop Capture Button
            elif event == Keys.STOP_CAPTURE:
                # Signal 
                log.info("Pressed STOP_CAPTURE")
                print("Ending Capture...")
                
                thread_stop.set()

            # Home Button
            elif event == Keys.GO_HOME:
                print("Pressed GO_HOME")

                # Change is_running_home flag
                is_running_home = True

                # Disable All Capture Controller Keys
                window[Keys.START_CAPTURE].update(disabled=True)
                window[Keys.STOP_CAPTURE].update(disabled=True)
                window[Keys.GO_HOME].update(disabled=True)
                
                thread = threading.Thread(target=run_home, args=(event, values, log, thread_done), daemon=True)
                thread.start()

            # ----- Thread Manager -----
            # Check if thread is completed
            if thread_done.is_set():
                if is_running_capture:
                    # Change flag to False
                    is_running_capture = False
                    # Print thread close message
                    if thread_stop.is_set():
                        log.say("Capture Terminated")
                    else: 
                        log.say("Capture Completed")
                    # Reopening camera in main()
                    camera = PiCamera()
                    log.say("Camera Opened")
                elif is_running_home:
                    # Change flag to False
                    is_running_home = False
                    # Print thread close message
                    log.say("Homing Completed")

                # Enable/disable Capture Controller Buttons
                # Enable "Start Capture" button
                window[Keys.START_CAPTURE].update(disabled=False)
                # Disable "End Capture" button
                window[Keys.STOP_CAPTURE].update(disabled=True)
                # Enable "Home" button
                window[Keys.GO_HOME].update(disabled=False)
                thread_done.clear()
                thread_stop.clear()
                thread.join(timeout=1)
            
            # ----- Queue manager -----
            # Sends message to output window
            try:
                while True:
                    msg = output_queue.get_nowait()
                    print(msg)
            except queue.Empty:
                pass
    # Safe Teardown
    finally:
        if camera:
            camera.close()
            print("Camera Closed")
        printer.close_printer()
        if window:
            window.close()
            print("Window Closed")

    return

if __name__ == "__main__":
    main()