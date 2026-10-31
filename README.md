# Pc-Checker-with-Python

A small console tool that prints a hardware report for the computer it runs on and saves the report as a `.txt` file.

> **Notice:** All results may differ from the actual hardware. Always verify with the physical hardware as well.

## What it shows

| Section | Details |
|---|---|
| System | OS, version, architecture, Python version |
| Motherboard & BIOS | System and board model, BIOS version and date (Windows) |
| CPU | Name, socket, cache, cores/threads, frequency, usage |
| Memory | Totals, plus each module: type, form factor, size, speed, maker, part number (Windows) |
| GPU | Name, PCI ID, driver version (Windows) |
| Disk | Model, type (SSD/HDD), bus, size, health, partitions |
| Battery | Level and charging state (if present) |
| Accessories | USB/Bluetooth keyboards and mice, active audio devices, paired Bluetooth devices, other USB devices (Windows) |
| Hardware Name Check | Compares hardware names from BIOS and Windows and flags mismatches |

Sizes are shown as binary units (KiB, MiB, GiB). Disk sizes are shown in both decimal GB and binary GiB.

## What it does not collect

- Serial numbers
- Computer name
- IP or MAC addresses

The program contains no networking code. The report is written only to the local disk. Read the source to confirm.

If you share a report, note that the names of paired Bluetooth devices can include a person's name. Set `SHOW_BLUETOOTH_NAMES = False` at the top of the script to hide them.

## Requirements

- Windows 10/11 for the full report (Linux and macOS give a reduced report)
- Python 3 (developed and run with Python 3.14)
- [`psutil`](https://pypi.org/project/psutil/)

## Usage

```bash
pip install psutil
python "Pc Checker.py"
```

On Windows you can also double-click `Run PcChecker.bat`. It installs `psutil` if it is missing and starts the script.

Reports are saved next to the script, in a folder named after the motherboard:

```
Pc Checker/
├── Pc Checker.py
├── Run PcChecker.bat
└── LENOVO LNVNB161216/
    └── PcChecker_20261031_103000.txt
```

Machines with the same motherboard model share one folder. Files are told apart by the date and time in the name.

## Limitations

- Values come from the BIOS and Windows, not from direct hardware probing. A device can report wrong values.
- The Hardware Name Check compares sources that often share the same origin. A mismatch means the sources disagree, not that a part is fake, and a match does not prove a part is genuine. Cross-check with tools such as CPU-Z, HWiNFO and GPU-Z.
- Reading raw BIOS data may need Administrator rights. If a check shows `UNVERIFIED`, try running as Administrator.
- GPU memory reported by Windows may be inaccurate.
- Many USB devices report only a generic name such as `USB Input Device`. The vendor and product ID is shown so the device can be looked up.
- Windows Smart App Control can block unsigned `.exe` files built with PyInstaller, so this project is run as a `.py` script.
