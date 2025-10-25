#!/usr/bin/env python3
"""
Graphical User Interface based off the version created by Johnny Duong
Author: Darren Lee
TODO:

"""
from datetime import datetime
from picamera.array import PiRGBArray, PiBayerArray
from picamera import PiCamera
from io import BytesIO
from PIL import Image
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
import well_location_calculator as wlc

# ===== Globals =====
frame_bytes = None
crosshair_radius = None
crosshair_on = True

# ===== GUI KEYS =====
class Keys:
    TAB_GROUP = "-TAB_GROUP-"
    # ===== RUN CAPTURE TAB (1) =====
    TAB_1 = "-TAB_1-"
    # ----- Capture Settings -----
    INPUT_CSV = "-CSV_INPUT-"
    NUM_COLS = "-COL-"
    NUM_ROWS = "-ROW-"
    OUTPUT_DIR = "-OUTPUT_DIR_INPUT-"
    OUTPUT_PREFIX = "-OUTPUT_PREFIX-"
    OUTPUT_SUFFIX = "-OUTPUT_SUFFIX-"
    OUTPUT_PREVIEW = "-OUTPUT_PREVIEW-"
    ZSTACK_ON = "-ZSTACK_ON-"
    ZSTACK_COUNT = "-ZSTACK_COUNT-"
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

    # ===== MANUAL MODE TAB (2) =====
    TAB_2 = "-TAB_2-"
    TAB_2_TITLE = "-TAB_2_TITLE-"
    # ----- Preview Overlay -----
    IMAGE = "-IMAGE-"
    SHOW_IMAGE = "-SHOW_IMAGE-"
    RADIUS = "-RADIUS-"
    CROSSHAIR_ON = "-CROSSHAIR_ON-"
    # ----- Manual Controller -----
    MANUAL_MOVE_GROUP = {
        "-MOVE_DUMMY-",
        "-X_POS-",
        "-X_NEG-",
        "-Y_POS-",
        "-Y_NEG-",
        "-Z_POS-",
        "-Z_NEG-",
    }
    MOVE_DUMMY = "-MOVE_DUMMY-"
    X_POS = "-X_POS-"
    X_NEG = "-X_NEG-"
    Y_POS = "-Y_POS-"
    Y_NEG = "-Y_NEG-"
    Z_POS = "-Z_POS-"
    Z_NEG = "-Z_NEG-"
    STEP_01 = "-STEP_SIZE_0.10mm-"
    STEP_05 = "-STEP_SIZE_0.50mm-"
    STEP_1 = "-STEP_SIZE_1.00mm-"
    STEP_5 = "-STEP_SIZE_5.00mm-"
    STEP_10 = "-STEP_SIZE_10.00mm-"
    PREVIEW_OVERLAY_ON = "-PREVIEW_OVERLAY_ON-"
    CURRENT_POSITION_TEXT = "-CURRENT_POSITION_TEXT-"
    SAVE_CSV = "-SAVE_CSV-"
    SAVE_CSV_NAME = "-SAVE_CSV_NAME-"
    # ----- Corner Location Storage
    # Top Left Store 
    TL_X = "-TOP_LEFT_X-"
    TL_Y = "-TOP_LEFT_Y-"
    TL_Z = "-TOP_LEFT_Z-"
    TL_SAVE = "-TOP_LEFT_SAVE-"
    # Top Right Store 
    TR_X = "-TOP_RIGHT_X-"
    TR_Y = "-TOP_RIGHT_Y-"
    TR_Z = "-TOP_RIGHT_Z-"
    TR_SAVE = "-TOP_RIGHT_SAVE-"
    # Bottom Left Store 
    BL_X = "-BOTTOM_LEFT_X-"
    BL_Y = "-BOTTOM_LEFT_Y-"
    BL_Z = "-BOTTOM_LEFT_Z-"
    BL_SAVE = "-BOTTOM_LEFT_SAVE-"
    # Bottom Right Store 
    BR_X = "-BOTTOM_RIGHT_X-"
    BR_Y = "-BOTTOM_RIGHT_Y-"
    BR_Z = "-BOTTOM_RIGHT_Z-"
    BR_SAVE = "-BOTTOM_RIGHT_SAVE-"

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

def draw_crosshair(frame, circle_radius=50, color=(0, 255, 0), thickness=2):
    h, w = frame.shape[:2]
    center_x, center_y = w // 2, h // 2

    # Croshair Length
    length = 20

    cv2.line(frame, (center_x - length, center_y), (center_x + length, center_y), color, thickness)
    cv2.line(frame, (center_x, center_y - length), (center_x, center_y + length), color, thickness)
    cv2.circle(frame, (center_x, center_y), circle_radius, color, thickness)
    return frame

def convert_to_bytes(frame):
    img = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
    im_pil = Image.fromarray(img)
    with BytesIO() as output:
        im_pil.save(output, format="PNG")
        data = output.getvalue()
    return data

def run_manual(event, values, log, manual_queue, thread_done, thread_stop, thread_update, thread_ready):
    log.say("New Thread Opened")
    global frame_bytes
    global crosshair_radius
    global crosshair_on

    # Open Camera
    try:
        camera.close()
    except:
        pass
    camera = PiCamera()     # Define camera
    log.info("Camera Opened")

    # Load Camera Settings
    camera.resolution = (cfg.preview.width, cfg.preview.height)
    camera.rotation = cfg.rotation
    raw = PiRGBArray(camera)
    time.sleep(2)
    thread_ready.set()

    # Change printer positioning mode
    printer.rel_pos()
    while not thread_stop.is_set():
        try:
            command = manual_queue.get(timeout=0.1)
            log.info(f"Running G-code: {command}")
            printer.run_gcode(command)
            manual_queue.task_done()
            printer.wait()

            raw.truncate(0)
            camera.capture(raw, format="bgr", use_video_port=True)
            frame = raw.array

            if frame.shape[0] >= 360:
                frame = frame[:360, :, :].copy()
            else:
                print("Warning: Frame too short", frame.shape)
                continue

            # Draw crosshair
            if crosshair_on:
                frame = draw_crosshair(frame, circle_radius=crosshair_radius)

            # Convert to JPEG for faster GUI rendering
            img = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
            pil_img = Image.fromarray(img)
            with BytesIO() as output:
                pil_img.save(output, format="PNG")
                frame_bytes = output.getvalue()
            thread_update.set()
        except queue.Empty:
            continue

    camera.close()
    thread_done.set()

def run_home(event, values, log, thread_done):
    """
    """
    log.say("Homing...")
    printer.home()
    thread_done.set()

def run_capture(event, values, log, thread_done, thread_stop, preview_win_id):
    """
    """
    log.say("Loading auto-capture...")
    # Safely load camera
    log.info("Opening camera...")
    try:
        camera.close()
    except:
        pass
    camera = PiCamera()     # Define camera
    log.info("Camera opened successfully!")

    # Load Camera Settings
    log.info("Loading settings...")
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
    log.info("Settings loaded successfully!")

    # Safely grab printer connection
    ser = printer.get_printer()

    # Load Option Booleans
    preview_mode = bool(values[Keys.PREVIEW_MODE])
    verbose_mode = bool(values[Keys.VERBOSE_MODE])

    # Grab CSV Filename
    csv_file_path = values[Keys.INPUT_CSV]
    location_list = ioh.load_gcode_from_csv(csv_file=csv_file_path)

    # Intiializes to clear the plate
    log.say("Initializing...")
    # printer.show_stats()
    # Clear the plate
    log.info("Clearing...")
    printer.rel_pos()
    printer.run_gcode("G0 Z+40.00 F20000")
    log.debug("Sending 'G0 Z+40.00 F20000'")
    printer.wait()
    
    # Move to start
    printer.abs_pos()
    printer.run_gcode(f"{location_list[0]} F800")
    log.debug("Sending '{location_list[0]} F800'")
    printer.wait()

    # Start Message
    log.say("===== Process Starting! =====")

    # Cycles through each well in a snakelike pattern
    # Checks for even rows (pos) to determine well number
    even_row_flag = False
    rows = int(cfg.num_rows)
    cols = int(cfg.num_cols)
    well_count = rows * cols

    X = 0
    Y = 1
    Z = 2

    zstack_plus_minus = int(values[Keys.ZSTACK_COUNT]) if values[Keys.ZSTACK_ON] else 0
    for offset_num in range(0 - zstack_plus_minus , 1 + zstack_plus_minus):
        offset = cfg.zstack_step_distance * offset_num
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
            split_location = location.split("Z")
            offset_location = f"{split_location[0]}Z{float(split_location[1]) + offset}"
            log.debug(f"Location is {offset_location}")
            printer.run_gcode(f"{offset_location} F800")
            log.info(f'Cycle {cycle}/{well_count}: Going to Well Number {"%02d" % well_number}')
            printer.wait()
            time.sleep(float(cfg.move_sleep_time))

            # Take Picture
            if preview_mode is False:
                log.info(f"Starting capture cycle")           
                photo_file_path = ioh.get_photo_path(values[Keys.OUTPUT_DIR], values[Keys.OUTPUT_PREFIX], values[Keys.OUTPUT_SUFFIX], "%02d" % cycle)
                os.makedirs(os.path.dirname(photo_file_path), exist_ok=True)
                camera.capture(photo_file_path)
                capture_sleep_time = (camera.shutter_speed / 1_000_000 * float(cfg.sleep_multiplier)) + float(cfg.sleep_addition)
                log.debug(f"Sleeping for {capture_sleep_time} seconds")
                time.sleep(capture_sleep_time)
                log.say(f"[INFO] Captured image {cycle}/{well_count}")
                log.info(f"Saved image as {photo_file_path}")
            else:
                log.info(f"Starting capture cycle")           
                photo_file_path = ioh.get_photo_path(values[Keys.OUTPUT_DIR], values[Keys.OUTPUT_PREFIX], values[Keys.OUTPUT_SUFFIX], "%02d" % well_number)
                capture_sleep_time = (camera.shutter_speed / 1_000_000 * float(cfg.sleep_multiplier)) + float(cfg.sleep_addition)
                log.debug(f"Sleeping for {capture_sleep_time} seconds")
                time.sleep(capture_sleep_time)
                log.say(f"[INFO] No image captured (preview mode is ON)")
                log.info(f"Did not save image as {photo_file_path}")
            
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

    # Startup message
    print("Opening Flycam GUI...")
    
    # Try to close any unended processes from previous crashes/errors
    # Safely initializes a single camera instance
    try:
        camera.close()
    except:
        pass

    # ===== Printer Startup =====
    # Setup 3D Printer
    ser = printer.get_printer()

    print("Homing")
    printer.home()
    print("Done!")
    print("Opening Window")

    # ===== GUI Window Layout =====
    sg.theme("LightBrown2")
    # sg.set_options(font=('Courier',12))
    # ----- Tab 1 (Run Capture) -----
    # Advanced camera settings collapsible
    # Left column, core settings subsection
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
    # Right column, tuning settings sebsection
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
    # Camera settings subsection joiner
    tab_1_column_1_collapse_layout = sg.pin(sg.Column([[
        sg.Column(core_settings_col, vertical_alignment='top'),
        sg.VSeparator(),
        sg.Column(tuning_settings_col, vertical_alignment='top')
    ]], key=Keys.CAMERA_SECTION, visible=False))
    # Auto-capture subsection
    tab_1_column_1_layout = [
        [sg.Text("Input CSV"), sg.Push(), sg.Input(size=(40, 1), default_text=f"{os.getcwd() if not cfg.input_csv else cfg.input_csv}{'/location_file_snake_path.csv' if not cfg.input_csv else ''}", key=Keys.INPUT_CSV), sg.FileBrowse()],
        [sg.Text("Output Folder"), sg.Push(), sg.Input(size=(40, 1), default_text=f"{os.getcwd() if not cfg.output_dir else cfg.output_dir}{'/well_photos' if not cfg.output_dir else ''}", enable_events=True, key=Keys.OUTPUT_DIR), sg.FolderBrowse()],
        [sg.Text("Output Prefix"), sg.Push(), sg.Input(size=(40, 1), default_text=cfg.output_prefix, enable_events=True, key=Keys.OUTPUT_PREFIX)],
        [sg.Text("Output Suffix"), sg.Push(), sg.Input(size=(40, 1), default_text=cfg.output_suffix, enable_events=True, key=Keys.OUTPUT_SUFFIX)],
        [sg.Push(), sg.Text(f"{os.getcwd() if not cfg.output_dir else cfg.output_dir}{'/well_photos' if not cfg.output_dir else ''}/{cfg.output_prefix}wellXX_YYYY-MM-DD_hhmmss{cfg.output_suffix}.jpg", text_color='darkolivegreen', key=Keys.OUTPUT_PREVIEW)],
        # [sg.Text("Well Plate Size "), sg.Input(default_text=cfg.num_cols, size=(3, 1), key=Keys.NUM_COLS), sg.Text("columns x "),
        # sg.Input(default_text=cfg.num_rows, size=(3, 1), key=Keys.NUM_ROWS), sg.Text("rows")],
        [sg.VPush()],
        [sg.Text("▶ Camera Settings", enable_events=True, key=Keys.OPEN_SECTION)],
        [tab_1_column_1_collapse_layout],
        #[sg.VPush(background_color='orange')],
        [sg.Checkbox("Z-Stack", key=Keys.ZSTACK_ON), sg.Input(cfg.zstack_plus_minus_count, size=(4,1), key=Keys.ZSTACK_COUNT)],
        [sg.Text("Select Capture Mode")],
        [sg.Radio("Preview", group_id="MODE_GROUP", default=cfg.preview_by_default, key=Keys.PREVIEW_MODE),
        sg.Radio("Picture", group_id="MODE_GROUP", default=cfg.picture_by_default, key=Keys.PICTURE_MODE)],
        [sg.Button("▶ Start Capture", button_color=(None, 'darkolivegreen'), key=Keys.START_CAPTURE, disabled=True),
        sg.Button("■ Stop Capture", button_color=(None, 'darkred'), key=Keys.STOP_CAPTURE, disabled=True),
        sg.Button("⌂ Home", button_color=(None, 'darkgoldenrod'), key=Keys.GO_HOME)]
    ]
    # Auto-capture joiner
    tab_1_layout = [
        [sg.Text("Auto Capture", font=(None, 14, 'bold'))],
        [sg.Column(tab_1_column_1_layout, expand_y=True)]
    ]
    # ----- Tab 2 (Manual Mode) -----
    # Labels current printer position
    current_position_layout = [
        [sg.Push(), sg.Text(f"X: {printer.get_pos()['X']} Y: {printer.get_pos()['Y']} Z: {printer.get_pos()['Z']}", key=Keys.CURRENT_POSITION_TEXT), sg.Push()]
    ]
    # Step size for manual mode selection {0.1, 0.5, 1.0, 5.0, 10.0}
    step_selector_layout = [
        [sg.Push(),
        sg.Radio("±0.1mm", group_id="STEP_GROUP", default=False, key=Keys.STEP_01),
        sg.Radio("±1.0mm", group_id="STEP_GROUP", default=True, key=Keys.STEP_1),
        sg.Radio("±10mm", group_id="STEP_GROUP", default=False, key=Keys.STEP_10),
        sg.Push(),
        ],
        [sg.Push(),
        sg.Radio("±0.5mm", group_id="STEP_GROUP", default=False, key=Keys.STEP_05),
        sg.Radio("±5.0mm", group_id="STEP_GROUP", default=False, key=Keys.STEP_5),
        sg.Push(),
        ]
    ]
    # Right, left (±X) and forwards, backwards (±Y) controls subsection
    manual_controls_layout_xy = [
        [sg.Column([
            [sg.VPush()],
            [sg.Button("◀", size=(2,1), key=Keys.X_NEG)],
            [sg.VPush()],
        ], expand_y=True),
        sg.Column([
            [sg.Button("▲", size=(2,1), key=Keys.Y_POS)],
            [sg.Button("◎", size=(2,1), key=Keys.MOVE_DUMMY)],
            [sg.Button("▼", size=(2,1), key=Keys.Y_NEG)],
        ], expand_y=True),
        sg.Column([
            [sg.VPush()],
            [sg.Button("▶", size=(2,1), key=Keys.X_POS)],
            [sg.VPush()],
        ], expand_y=True)
        ] 
    ]
    # Up, down (±Z) controls subsection
    manual_controls_layout_z = [
        [sg.VPush()],
        [sg.Button("+Z", size=(3,1), key=Keys.Z_POS)],
        [sg.Button("-Z", size=(3,1), key=Keys.Z_NEG)],
        [sg.VPush()]
    ]
    # Controller buttons subsection joiner
    all_controls_layout = [
        [sg.VPush()],
        [sg.Text("CSV Name"), sg.Input("", size=(25,1), key=Keys.SAVE_CSV_NAME)],
        [sg.Button("Generate CSV", key=Keys.SAVE_CSV)],
        [sg.HorizontalSeparator()],
        [sg.Column(current_position_layout)],
        [sg.Column(step_selector_layout)],
        [sg.Column(manual_controls_layout_xy), sg.Column(manual_controls_layout_z, expand_y=True)],
    ]
    # Corner inputs
    # Top-left subsection
    top_left_layout = [
        [sg.Text("X:"), sg.Input("0.00", size=(6,1), key=Keys.TL_X)],
        [sg.Text("Y:"), sg.Input("0.00", size=(6,1), key=Keys.TL_Y)],
        [sg.Text("Z:"), sg.Input("0.00", size=(6,1), key=Keys.TL_Z)],
        [sg.Button("Save Current Position", key=Keys.TL_SAVE)]
    ]
    # Top-right subsection
    top_right_layout = [
        [sg.Text("X:"), sg.Input("0.00", size=(6,1), key=Keys.TR_X)],
        [sg.Text("Y:"), sg.Input("0.00", size=(6,1), key=Keys.TR_Y)],
        [sg.Text("Z:"), sg.Input("0.00", size=(6,1), key=Keys.TR_Z)],
        [sg.Button("Save Current Position", key=Keys.TR_SAVE)]
    ]
    # Bottom-left subsection
    bottom_left_layout = [
        [sg.Text("X:"), sg.Input("0.00", size=(6,1), key=Keys.BL_X)],
        [sg.Text("Y:"), sg.Input("0.00", size=(6,1), key=Keys.BL_Y)],
        [sg.Text("Z:"), sg.Input("0.00", size=(6,1), key=Keys.BL_Z)],
        [sg.Button("Save Current Position", key=Keys.BL_SAVE)]
    ]
    # Bottom-right subsection
    bottom_right_layout = [
        [sg.Text("X:"), sg.Input("0.00", size=(6,1), key=Keys.BR_X)],
        [sg.Text("Y:"), sg.Input("0.00", size=(6,1), key=Keys.BR_Y)],
        [sg.Text("Z:"), sg.Input("0.00", size=(6,1), key=Keys.BR_Z)],
        [sg.Button("Save Current Position", key=Keys.BR_SAVE)]
    ]
    # Corner inputs subsection joiner
    corners_input_layout = [
        [sg.Frame("Top Left", top_left_layout), sg.Push(), sg.Frame("Top Right", top_right_layout)],
        [sg.Frame("Bottom Left",bottom_left_layout), sg.Push(), sg.Frame("Bottom Right", bottom_right_layout)],
    ]
    # Manual controller joiner
    tab_2_layout =[
        [sg.Text("Manual Controller", font=(None, 14, 'bold'))],
        [sg.Push(), sg.pin(sg.Column([[sg.Image(filename="", visible=False, key=Keys.IMAGE)]], key=Keys.SHOW_IMAGE)), sg.Push()],
        [sg.Push(), sg.Checkbox("Crosshair", default=True, enable_events=True, key=Keys.CROSSHAIR_ON), sg.Text("Radius"), sg.Slider((10,200), 180, 1, orientation="h", enable_events=True, key=Keys.RADIUS), sg.Push()],
        [sg.Column(all_controls_layout), sg.VerticalSeparator(), sg.Column(corners_input_layout)]
        ]
    # ----- Define Window Layout -----
    layout = [ [sg.TabGroup([
        [sg.Tab("Auto Capture", tab_1_layout)],
        [sg.Tab("Manual Controller", tab_2_layout)]
        ], enable_events=True, key=Keys.TAB_GROUP)],
        [sg.Checkbox("Verbose", default=cfg.verbose_mode, key=Keys.VERBOSE_MODE)],
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
    thread_update = threading.Event()
    thread_ready = threading.Event()
    
    # ----- Flags and variables ----- 
    # Boolean flag to know if which thread is running
    is_running_capture = False
    is_running_home = False
    is_running_manual = False

    opened = False
    # ----- Logger setup -----
    output_queue = queue.Queue()
    log = Logger(verbose=True, output_queue=output_queue)

    # ----- Manual Controller setup -----
    manual_queue = queue.Queue()

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

                # Disable Other Tab Groups
                window[Keys.TAB_GROUP].Widget.tab(1, state="disabled")
                window[Keys.TAB_GROUP].Widget.tab(1, text="✕ Locked")

                # Start threaded capture
                thread = threading.Thread(target=run_capture, args=(event, values, log, thread_done, thread_stop, preview_win_id), name="Capture", daemon=True)
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

                # Disable Other Tab Groups
                window[Keys.TAB_GROUP].Widget.tab(1, state="disabled")
                window[Keys.TAB_GROUP].Widget.tab(1, text="✕ Locked")
                
                thread = threading.Thread(target=run_home, args=(event, values, log, thread_done), name="GoHome", daemon=True)
                thread.start()
            
            # Manual Controller
            elif event == Keys.TAB_GROUP:
                print("Pressed TAB_GROUP")
                selected_tab_group = values[Keys.TAB_GROUP]
                print(selected_tab_group)
                if selected_tab_group == "Auto Capture" and is_running_manual:
                    # Hide Image Preview
                    window[Keys.SHOW_IMAGE].update(visible=False)

                    print("Sending thread_stop")
                    thread_stop.set()
                elif selected_tab_group == "Manual Controller":
                    print("Switched to Manual Mode Tab")

                    # Close Camera Settings Dropdown if opened when switching tabs
                    if opened:
                        opened = not opened
                        window[Keys.OPEN_SECTION].update("▼ Camera Settings" if opened else "▶ Camera Settings")
                        window[Keys.CAMERA_SECTION].update(visible=opened)

                    # Show Image Preview
                    window[Keys.SHOW_IMAGE].update(visible=True)
                    manual_queue.put("M400")

                    # Change is_running_manual flag
                    is_running_manual = True

                    # Update current position text
                    window[Keys.CURRENT_POSITION_TEXT].update(value=f"X: {printer.get_pos()['X']} Y: {printer.get_pos()['Y']} Z: {printer.get_pos()['Z']}")
                    
                    # Show Image element
                    window[Keys.IMAGE].update(visible=True)
                    
                    # Start thread
                    thread = threading.Thread(target=run_manual, args=(event, values, log, manual_queue, thread_done, thread_stop, thread_update, thread_ready), name="ManualController", daemon=True)
                    thread.start()
            
            elif event == Keys.CROSSHAIR_ON:
                global crosshair_on
                crosshair_on = values[Keys.CROSSHAIR_ON]
                manual_queue.put("M400")

            elif event == Keys.RADIUS:
                global crosshair_radius
                crosshair_radius = int(values[Keys.RADIUS])



            elif event in Keys.MANUAL_MOVE_GROUP:
                print("Clicked movement key!")
                window[Keys.X_POS].update(disabled=True)
                window[Keys.X_NEG].update(disabled=True)
                window[Keys.Y_POS].update(disabled=True)
                window[Keys.Y_NEG].update(disabled=True)
                window[Keys.Z_POS].update(disabled=True)
                window[Keys.Z_NEG].update(disabled=True)

                if values[Keys.STEP_01]:
                    step_size = 0.1
                elif values[Keys.STEP_05]:
                    step_size = 0.5
                elif values[Keys.STEP_1]:
                    step_size = 1.0
                elif values[Keys.STEP_5]:
                    step_size = 5.0
                elif values[Keys.STEP_10]:
                    step_size = 10.0
                # feedrate = min(max(step_size * 500, 100), 3000)
                feedrate = 800
                if event == Keys.MOVE_DUMMY:
                    log.debug("Pressed MOVE_DUMMY")
                    manual_queue.put("M400")

                elif event == Keys.X_POS:
                    log.debug("Pressed X_POS")
                    manual_queue.put(f"G1 X+{step_size:.3f} F{feedrate:.0f}")
                elif event == Keys.X_NEG:
                    log.debug("Pressed X_NEG")
                    manual_queue.put(f"G1 X-{step_size:.3f} F{feedrate:.0f}")
                
                elif event == Keys.Y_POS:
                    log.debug("Pressed Y_POS")
                    manual_queue.put(f"G1 Y+{step_size:.3f} F{feedrate:.0f}")
                elif event == Keys.Y_NEG:
                    log.debug("Pressed Y_NEG")
                    manual_queue.put(f"G1 Y-{step_size:.3f} F{feedrate:.0f}")
                
                elif event == Keys.Z_POS:
                    log.debug("Pressed Z_POS")
                    manual_queue.put(f"G1 Z+{step_size:.3f} F{feedrate:.0f}")
                elif event == Keys.Z_NEG:
                    log.debug("Pressed Z_NEG")
                    manual_queue.put(f"G1 Z-{step_size:.3f} F{feedrate:.0f}")

            elif event == Keys.TL_SAVE:
                positions = printer.get_pos()
                window[Keys.TL_X].update(positions['X'])
                window[Keys.TL_Y].update(positions['Y'])
                window[Keys.TL_Z].update(positions['Z'])
            
            elif event == Keys.TR_SAVE:
                positions = printer.get_pos()
                window[Keys.TR_X].update(positions['X'])
                window[Keys.TR_Y].update(positions['Y'])
                window[Keys.TR_Z].update(positions['Z'])
            
            elif event == Keys.BL_SAVE:
                positions = printer.get_pos()
                window[Keys.BL_X].update(positions['X'])
                window[Keys.BL_Y].update(positions['Y'])
                window[Keys.BL_Z].update(positions['Z'])
            
            elif event == Keys.BR_SAVE:
                positions = printer.get_pos()
                window[Keys.BR_X].update(positions['X'])
                window[Keys.BR_Y].update(positions['Y'])
                window[Keys.BR_Z].update(positions['Z'])
            
            elif event == Keys.SAVE_CSV:
                print("Pressed SAVE_CSV")
                tl = [
                    float(values[Keys.TL_X]),
                    float(values[Keys.TL_Y]),
                    float(values[Keys.TL_Z])]
                tr = [
                    float(values[Keys.TR_X]),
                    float(values[Keys.TR_Y]),
                    float(values[Keys.TR_Z])]
                bl = [
                    float(values[Keys.BL_X]),
                    float(values[Keys.BL_Y]),
                    float(values[Keys.BL_Z])]
                br = [
                    float(values[Keys.BR_X]),
                    float(values[Keys.BR_Y]),
                    float(values[Keys.BR_Z])]
                filename = f"{os.getcwd() if not cfg.output_dir else cfg.output_dir}/{values[Keys.SAVE_CSV_NAME]}.csv"
                wlc.generate_csv(cfg.num_rows, cfg.num_cols, tl, tr, bl, br, filename)

            # ----- Thread done manager -----
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

                elif is_running_home:
                    # Change flag to False
                    is_running_home = False
                    # Print thread close message
                    log.say("Homing Completed")
                elif is_running_manual:
                    is_running_manual = False
                    log.say("Manual Controller Closed")


                # Enable/disable Capture Controller Buttons
                # Enable "Start Capture" button
                window[Keys.START_CAPTURE].update(disabled=False)
                # Disable "End Capture" button
                window[Keys.STOP_CAPTURE].update(disabled=True)
                # Enable "Home" button
                window[Keys.GO_HOME].update(disabled=False)
                # Enable Other Tab Groups
                window[Keys.TAB_GROUP].Widget.tab(1, state="normal")
                window[Keys.TAB_GROUP].Widget.tab(1, text="Manual Controller")
                thread_done.clear()
                thread_stop.clear()
                thread_update.clear()
                thread_ready.clear()
                thread.join(timeout=1)

            # ----- Thread update manager -----
            if is_running_manual:
                if thread_update.is_set():
                    window[Keys.CURRENT_POSITION_TEXT].update(value=f"X: {printer.get_pos()['X']} Y: {printer.get_pos()['Y']} Z: {printer.get_pos()['Z']}")
                    thread_update.clear()

                    window[Keys.X_POS].update(disabled=False)
                    window[Keys.X_NEG].update(disabled=False)
                    window[Keys.Y_POS].update(disabled=False)
                    window[Keys.Y_NEG].update(disabled=False)
                    window[Keys.Z_POS].update(disabled=False)
                    window[Keys.Z_NEG].update(disabled=False)

                    global frame_bytes
                    if frame_bytes:
                        print("Bytes length:", len(frame_bytes) if frame_bytes else None)
                        try:
                            window[Keys.IMAGE].update(data=frame_bytes)
                        except Exception as e:
                            print("Update failed", e)

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