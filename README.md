# Pc-Checker-with-Python

A small tool that shows a hardware report for the computer it runs on, in a tabbed window or as plain text, and can save the report as a `.txt` file.

> **Notice:** All results may differ from the actual hardware. Always verify with the physical hardware as well.

## What it shows

| Tab / section | Details |
|---|---|
| System | OS, version, architecture, Python version |
| Motherboard | System and board model, BIOS version and date (Windows) |
| CPU | Name, socket, cache, cores/threads, frequency, usage |
| Memory | Totals, plus each module: type, form factor, size, speed, maker, part number (Windows) |
| GPU | Name, PCI ID, driver version (Windows) |
| Disk | Model, type (SSD/HDD), bus, size, health, partitions |
| Battery | Level and charging state (if present) |
| Accessories | USB/Bluetooth keyboards and mice, active audio devices, paired Bluetooth devices, other USB devices (Windows) |
| Name Check | Compares hardware names from BIOS and Windows and flags mismatches (Windows) |

Sizes are shown as binary units (KiB, MiB, GiB). Disk sizes are shown in both decimal GB and binary GiB.

Tabs with changing values (System time, CPU, Memory, Disk, Battery, Accessories) update by themselves while the tab is open. Motherboard, GPU and Name Check are read once, and **Refresh** reads everything again.

## What it does not collect

- Serial numbers
- Computer name
- IP or MAC addresses

The program contains no networking code. A report is written to the local disk only when you save it. Read the source to confirm.

If you share a report, note that the names of paired Bluetooth devices can include a person's name. Set `SHOW_BLUETOOTH_NAMES = False` at the top of the script to hide them.

## Requirements

- Windows 10/11 for the full report (Linux and macOS give a reduced report)
- Python 3 (developed and run with Python 3.14), including tkinter for the window (the python.org installer includes it)
- [`psutil`](https://pypi.org/project/psutil/)

## Usage

On Windows, double-click `Run.bat`. It installs `psutil` if it is missing and opens the window.

Or from a terminal:

```bash
pip install psutil
python "Pc Checker.py"
```

For the plain text mode, without the window:

```bash
python "Pc Checker.py" --console
```

In the window, **Pause live** freezes the updating, **Save this tab** saves the tab you are looking at, and **Save all** saves the full report. Both save buttons first pause the live updates at the moment you press them, so the file holds exactly the values shown at that moment, then open a save dialog where you choose the folder and the file name. Live updating resumes after you save or cancel. In text mode the report is saved automatically.

The save dialog starts in a folder named after the motherboard, next to the script, and remembers the last folder you used. Saved reports in that folder look like this:

```
Pc Checker/
├── Pc Checker.py
├── Run.bat
└── LENOVO LNVNB161216/
    └── PcChecker_20261101_103000.txt
```

Machines with the same motherboard model share one folder. Files are told apart by the date and time in the name. If you rename `Pc Checker.py`, update the name inside `Run.bat` too.

## Settings

At the top of `Pc Checker.py`:

```python
SAVE_REPORT = True            # text mode: save the report automatically
GUI_AUTO_SAVE = False         # window: save automatically when it opens
SHOW_BLUETOOTH_NAMES = True   # set False to hide paired Bluetooth device names
```

## Limitations

- Values come from the BIOS and Windows, not from direct hardware probing. A device can report wrong values.
- The Name Check compares sources that often share the same origin. A mismatch means the sources disagree, not that a part is fake, and a match does not prove a part is genuine. Cross-check with tools such as CPU-Z, HWiNFO and GPU-Z.
- Reading raw BIOS data may need Administrator rights. If a check shows `UNVERIFIED`, try running as Administrator.
- GPU memory reported by Windows may be inaccurate.
- The CPU tab shows frequency estimated from Windows performance counters. On Windows with a non-English display language the counter names can differ, and then the tab falls back to the frequency reported by the system, which may not show turbo.
- Temperature is not read. Use a tool such as HWMonitor for that.
- Many USB devices report only a generic name such as `USB Input Device`. The vendor and product ID is shown so the device can be looked up.
- Windows Smart App Control can block unsigned `.exe` files built with PyInstaller, so this project is run as a `.py` script.
