import numpy as np
import csv

def _bilinear_grid_calculation(num_rows, num_cols, tl, tr, bl, br):
    positions = []

    tl = np.array(tl)
    tr = np.array(tr)
    bl = np.array(bl)
    br = np.array(br)

    well_id = 1

    for r in range(num_rows):
        v = r / (num_rows - 1)

        col_range = range(num_cols)
        if r % 2 == 1:
            col_range = reversed(col_range)
        
        for c in col_range:
            u = c / (num_cols - 1)

            top = (1 - u) * tl + u * tr
            bottom = (1 - u) * bl + u * br
            pos = (1 - v) * top + v * bottom

            x, y, z = np.round(pos, 3)
            positions.append((well_id, x, y, z))
            well_id += 1
    
    return positions

def generate_csv(num_rows, num_cols, tl, tr, bl, br, filename):
    positions = _bilinear_grid_calculation(num_rows, num_cols, tl, tr, bl, br)

    with open(filename, 'w', newline='') as csvfile:
        writer = csv.writer(csvfile)
        writer.writerow(['cycle', 'X', 'Y', 'Z'])
        writer.writerows(positions)
