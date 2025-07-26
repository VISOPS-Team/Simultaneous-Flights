import csv
import os
import shutil
import subprocess
import json
from collections import defaultdict

def group_photos_by_drone(csv_path):
    data_dict = defaultdict(list)

    with open(csv_path, mode='r', newline='', encoding='utf-8') as infile:
        reader = csv.DictReader(infile)
        for row in reader:
            serial = row['xmp.drone-dji:DroneSerialNumber'].strip()
            if not serial:
                print(f"Missing DroneSerialNumber in row: {row}")
            data_dict[serial].append(row)

    if len(data_dict) == 1:
        print("Single drone flight.")
    else:
        print("Simultaneous flight.")

    print("\nPhoto count per drone:")
    for serial, data in data_dict.items():
        print(f"  {serial}: {len(data)} photo(s)")

        output_file = f"drone_{serial}.csv"
        with open(output_file, mode='w', newline='', encoding='utf-8') as outfile:
            writer = csv.DictWriter(outfile, fieldnames=data[0].keys())
            writer.writeheader()
            writer.writerows(data)
        print(f"Data for serial number {serial} saved to '{output_file}'.")

    return data_dict

def parse_mrk_file(mrk_path):
    photo_names = set()
    with open(mrk_path, 'r') as f:
        for line in f:
            parts = line.strip().split()
            if parts:
                filename = parts[0].strip()
                if filename.lower().endswith('.jpg'):
                    photo_names.add(filename)
    return photo_names

def find_and_organize_logs(base_dir, photo_groups):
    rtk_folder = os.path.join(base_dir, 'rtk')
    if not os.path.isdir(rtk_folder):
        print("No 'rtk/' folder found.")
        return

    mrk_files = [f for f in os.listdir(rtk_folder) if f.lower().endswith('.mrk')]

    for mrk_file in mrk_files:
        mrk_path = os.path.join(rtk_folder, mrk_file)
        mrk_photos = parse_mrk_file(mrk_path)

        log_prefix = mrk_file.split('_')[0]

        matched_serial = None
        for serial, rows in photo_groups.items():
            drone_photos = set(row['filename'].strip() for row in rows)
            if mrk_photos & drone_photos:
                matched_serial = serial
                break

        if matched_serial:
            matched_log = None
            for ext in ['.bin', '.obs']:
                for f in os.listdir(rtk_folder):
                    if f.startswith(log_prefix) and f.lower().endswith(ext):
                        matched_log = f
                        break
                if matched_log:
                    break

            output_folder = os.path.join(base_dir, f'drone_{matched_serial}')
            os.makedirs(output_folder, exist_ok=True)

            shutil.copy(mrk_path, output_folder)
            print(f"✔ Copied MRK to {output_folder}")

            if matched_log:
                shutil.copy(os.path.join(rtk_folder, matched_log), output_folder)
                print(f"✔ Copied {matched_log} for drone {matched_serial}")
            else:
                print(f"⚠ Warning: No .BIN or .OBS file found for MRK prefix '{log_prefix}'")
        else:
            print(f"✖ No drone match found for MRK file: {mrk_file}")

def run_ppk_on_drones(base_dir, rinex_path, exif_json_path):
    for folder in os.listdir(base_dir):
        if folder.startswith("drone_") and os.path.isdir(os.path.join(base_dir, folder)):
            drone_path = os.path.join(base_dir, folder)
            sol_output = os.path.join(drone_path, 'sol')
            os.makedirs(sol_output, exist_ok=True)

            command = [
                'ppk',
                '-b', f'"{rinex_path}"',
                '-r', f'"{drone_path}"',
                '-i', f'"{exif_json_path}"',
                '-o', f'"{sol_output}"'
            ]

            command_str = ' '.join(command)
            print(f"\n▶ Running PPK for {folder}...")
            print("Command:", command_str)

            try:
                result = subprocess.run(command_str, check=True, capture_output=True, text=True, shell=True)
                print(f"✅ PPK finished for {folder}\n{result.stdout}")
            except subprocess.CalledProcessError as e:
                print(f"❌ PPK failed for {folder}\n{e.stderr}")

def merge_ppk_solutions(base_dir):
    final_dir = os.path.join(base_dir, 'solution_final')
    os.makedirs(final_dir, exist_ok=True)

    final_geotags_txt = os.path.join(final_dir, 'geotags.txt')
    final_geotags_json = os.path.join(final_dir, 'geotags.json')
    final_stats_json = os.path.join(final_dir, 'stats.json')

    merged_geotags_dict = {}
    merged_ppk_entries = []
    fix_total = float_total = spp_total = all_total = 0
    stats_precise_position = None  # Will store from first file

    with open(final_geotags_txt, 'w', encoding='utf-8') as out_txt:
        for folder in os.listdir(base_dir):
            if folder.startswith("drone_") and os.path.isdir(os.path.join(base_dir, folder)):
                sol_dir = os.path.join(base_dir, folder, 'sol')

                # 1. Merge geotags.txt — append directly, ensure each file ends with a newline
                geotags_txt_path = os.path.join(sol_dir, 'geotags.txt')
                if os.path.isfile(geotags_txt_path):
                    with open(geotags_txt_path, 'r', encoding='utf-8') as in_txt:
                        for line in in_txt:
                            if not line.endswith('\n'):
                                line += '\n'
                            out_txt.write(line)

                # 2. Merge geotags.json
                geotags_json_path = os.path.join(sol_dir, 'geotags.json')
                if os.path.isfile(geotags_json_path):
                    with open(geotags_json_path, 'r', encoding='utf-8') as f:
                        geotag_entries = json.load(f)
                        merged_geotags_dict.update(geotag_entries)

                # 3. Merge stats.json
                stats_json_path = os.path.join(sol_dir, 'stats.json')
                if os.path.isfile(stats_json_path):
                    with open(stats_json_path, 'r', encoding='utf-8') as f:
                        stats = json.load(f)
                        merged_ppk_entries.extend(stats.get('ppk', []))
                        geotags_stats = stats.get('geotags', {})

                        fix_total += geotags_stats.get('fix', 0)
                        float_total += geotags_stats.get('float', 0)
                        spp_total += geotags_stats.get('spp', 0)
                        all_total += geotags_stats.get('all', 0)

                        if not stats_precise_position:
                            stats_precise_position = stats.get('precisePosition', None)

    # Write merged geotags.json
    with open(final_geotags_json, 'w', encoding='utf-8') as f:
        json.dump(merged_geotags_dict, f, indent=2)

    # Write merged stats.json
    merged_stats = {
        "ppk": merged_ppk_entries,
        "precisePosition": stats_precise_position or {},
        "geotags": {
            "fix": fix_total,
            "float": float_total,
            "spp": spp_total,
            "all": all_total
        }
    }

    with open(final_stats_json, 'w', encoding='utf-8') as f:
        json.dump(merged_stats, f, indent=2)

    print(f"\n✅ Final solution created in: {final_dir}")

# --- Main Execution ---
if __name__ == '__main__':
    print("=== Skycatch PPK Multi-Drone Processor ===")

    base_dir = os.path.abspath(os.path.dirname(__file__))
    csv_path = os.path.join(base_dir, 'exif', 'exif.csv')

    if not os.path.exists(csv_path):
        print(f"❌ Missing EXIF CSV: {csv_path}")
        exit(1)

    rinex_path = input("Enter full path to RINEX folder (-b): ").strip()
    exif_json_path = input("Enter full path to EXIF JSON (-i): ").strip()

    if not os.path.isdir(rinex_path):
        print(f"❌ Invalid RINEX path: {rinex_path}")
        exit(1)
    if not os.path.isfile(exif_json_path):
        print(f"❌ Invalid EXIF JSON file: {exif_json_path}")
        exit(1)

    photo_groups = group_photos_by_drone(csv_path)
    find_and_organize_logs(base_dir, photo_groups)
    run_ppk_on_drones(base_dir, rinex_path, exif_json_path)
    merge_ppk_solutions(base_dir)
