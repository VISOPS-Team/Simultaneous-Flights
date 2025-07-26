# Simultaneous-Flights

A tool designed to generate correct PPK geotags for simultaneous drone flights, enabling accurate positioning for multi-drone operations.

## Features

1. Generate separate EXIF files for each drone to handle simultaneous captures.
2. Automatically identify and organize drone logs based on drone IDs or metadata.
3. Execute the PPK engine individually for each drone flight.
4. Merge the final PPK solutions into a unified output, ready for processing in your pipeline or Pix4D.

## Requirements

- **Python 3.x**  
  Make sure Python is installed and accessible from your system’s PATH.

- **Dependencies**  
  This script uses the following standard Python libraries:
  - `os`
  - `csv`
  - `shutil`
  - `subprocess`

- **Other Requirements**
  - Raw dataset exported from the pipeline
  - Installed and working PPK engine

## Usage

1. Download or clone the script (`ppk_simultaneous.py`)
2. Place it in your working directory
3. Open a terminal and run:

   ```bash
   python ppk_simultaneous.py

4. Input directories for rinex, rtk, and exif.json
