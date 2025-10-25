import csv

from datetime import datetime

def load_gcode_from_csv(csv_file):
    with open(csv_file, newline="") as f:
        reader = csv.DictReader(f)
        return [f"G0X{row['X']}Y{row['Y']}Z{row['Z']}" for row in reader]

def get_photo_path(output_directory, output_prefix, output_suffix, well_number, z_lvl=0):
    current_time = datetime.now()
    timestamp = current_time.strftime("%Y-%m-%d_%H%M%S")
    filename = f"{output_prefix}well{well_number}_{timestamp}{output_suffix}.jpg"
    full_path = f"{output_directory}/{filename}"
    return full_path