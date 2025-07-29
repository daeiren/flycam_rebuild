import yaml
import os

class Resolution:
    def __init__(self, width: int, height: int):
        self.width = int(width)
        self.height = int(height)

class DefaultsConfig:
    def __init__(self, file_path="config.yaml"):
        try: 
            with open(file_path, 'r') as file:
                config = yaml.safe_load(file)

            # Plate Defaults
            self.num_rows = config['plate']['rows']
            self.num_cols = config['plate']['columns']

            # Capture I/O Defaults
            self.input_csv = config['capture']['input_csv']
            self.output_dir = config['capture']['output_dir']
            self.output_prefix = config['capture']['output_prefix']
            self.output_suffix = config['capture']['output_suffix']

            # Camera Defaults
            self.preview = Resolution(**config['camera']['resolution']['preview'])
            self.picture = Resolution(**config['camera']['resolution']['picture'])
            # Core Settings
            self.rotation = config['camera']['core']['rotation']
            self.framerate = config['camera']['core']['framerate']
            self.iso = config['camera']['core']['iso']
            self.shutter = config['camera']['core']['shutter']
            self.sleep_multiplier = config['camera']['core']['sleep_multiplier']
            self.sleep_addition = config['camera']['core']['sleep_addition']
            self.exposure_mode = config['camera']['core']['exposure_mode']
            self.awb_mode = config['camera']['core']['awb_mode']
            # Tuning Settings
            self.brightness = config['camera']['tuning']['brightness']
            self.contrast = config['camera']['tuning']['contrast']
            self.sharpness = config['camera']['tuning']['sharpness']
            self.saturation = config['camera']['tuning']['saturation']
            self.red_gain = config['camera']['tuning']['red_gain']
            self.blue_gain = config['camera']['tuning']['blue_gain']

            # Misc Defaults
            self.preview_by_default = config['misc']['preview_by_default']
            self.picture_by_default = not self.preview_by_default
            self.verbose_mode = config['misc']['verbose']

            # Printer Connection
            self.printer_name = config['printer']['name']
            self.device_path = config['printer']['device_path']
            self.baudrate = config['printer']['baudrate']
            self.timeout_time = config['printer']['timeout_time']
            self.move_sleep_time = config['printer']['move_sleep_time']
            self.max_x = config['printer']['max']['x']
            self.max_y = config['printer']['max']['y']
            self.max_z = config['printer']['max']['z']
            self.max_speed = config['printer']['max']['speed']

        except FileNotFoundError:
            print(f"[ERROR] Config file '{file_path}' not found")
        except yaml.YAMLError as e:
            print(f"[ERROR] YAML parse error: {e}. Check your config file!")

script_dir = os.path.dirname(os.path.abspath(__file__))
config_path = os.path.join(script_dir, "config.yaml")
 
config = DefaultsConfig(file_path="config.yaml")

