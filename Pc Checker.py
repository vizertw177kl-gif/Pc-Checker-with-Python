import contextlib
import io
import json
import os
import platform
import re
import subprocess
import sys
from datetime import datetime
 
import psutil
 
SAVE_REPORT = True
GUI_AUTO_SAVE = False
SHOW_BLUETOOTH_NAMES = True
SHOW_HEADERS = True
NO_WINDOW = getattr(subprocess, "CREATE_NO_WINDOW", 0)
 
 
def _check_output(*args, **kwargs):
    kwargs.setdefault("stdin", subprocess.DEVNULL)
    if NO_WINDOW:
        kwargs.setdefault("creationflags", NO_WINDOW)
    return subprocess.check_output(*args, **kwargs)
 
RAM_TYPES = {
    20: "DDR",
    21: "DDR2",
    24: "DDR3",
    26: "DDR4",
    27: "LPDDR",
    28: "LPDDR2",
    29: "LPDDR3",
    30: "LPDDR4",
    34: "DDR5",
    35: "LPDDR5",
}
 
DISK_MEDIA = {0: "Unspecified", 3: "HDD", 4: "SSD", 5: "SCM"}
DISK_BUS = {
    1: "SCSI", 3: "ATA", 7: "USB", 8: "RAID", 10: "SAS",
    11: "SATA", 12: "SD", 13: "MMC", 17: "NVMe",
}
DISK_HEALTH = {0: "Healthy", 1: "Warning", 2: "Unhealthy", 5: "Unknown"}
 
 
class Tee:
    def __init__(self, *streams):
        self.streams = streams
 
    def write(self, data):
        for s in self.streams:
            s.write(data)
 
    def flush(self):
        for s in self.streams:
            s.flush()
 
 
def get_size(bytes_value, suffix="B"):
    factor = 1024
    for unit in ["", "Ki", "Mi", "Gi", "Ti", "Pi"]:
        if bytes_value < factor:
            return f"{bytes_value:.1f} {unit}{suffix}"
        bytes_value /= factor
    return f"{bytes_value:.1f} Ei{suffix}"
 
 
def get_size_decimal(bytes_value, suffix="B"):
    factor = 1000
    for unit in ["", "k", "M", "G", "T", "P"]:
        if bytes_value < factor:
            return f"{bytes_value:.1f} {unit}{suffix}"
        bytes_value /= factor
    return f"{bytes_value:.1f} E{suffix}"
 
 
def get_size_both(bytes_value):
    return f"{get_size_decimal(bytes_value)} ({get_size(bytes_value)})"
 
 
def na(value):
    if value is None:
        return "N/A"
    text = str(value).strip()
    if text == "" or text.lower() in ("to be filled by o.e.m.", "default string"):
        return "N/A"
    return text
 
 
def lookup(table, value):
    if isinstance(value, int):
        return table.get(value, str(value))
    return na(value)
 
 
def run_powershell(command):
    out = _check_output(
        ["powershell", "-NoProfile", "-Command", command],
        text=True,
        stderr=subprocess.DEVNULL,
    )
    return [line.strip() for line in out.splitlines() if line.strip()]
 
 
def ps_json(command):
    full = (
        "[Console]::OutputEncoding=[Text.Encoding]::UTF8; "
        + command
        + " | ConvertTo-Json -Compress"
    )
    try:
        out = _check_output(
            ["powershell", "-NoProfile", "-Command", full],
            text=True,
            encoding="utf-8",
            stderr=subprocess.DEVNULL,
        ).strip()
        if not out:
            return []
        data = json.loads(out)
        return data if isinstance(data, list) else [data]
    except Exception:
        return []
 
 
def get_cpu_name():
    system = platform.system()
    try:
        if system == "Windows":
            names = run_powershell("(Get-CimInstance Win32_Processor).Name")
            if names:
                return names[0]
        elif system == "Darwin":
            return _check_output(
                ["sysctl", "-n", "machdep.cpu.brand_string"],
                text=True,
                stderr=subprocess.DEVNULL,
            ).strip()
        else:
            with open("/proc/cpuinfo") as f:
                for line in f:
                    if "model name" in line:
                        return line.split(":")[1].strip()
    except Exception:
        pass
    return platform.processor() or "Unknown Processor"
 
 
def get_gpu_info():
    system = platform.system()
    try:
        if system == "Darwin":
            out = _check_output(
                ["system_profiler", "SPDisplaysDataType"],
                text=True,
                stderr=subprocess.DEVNULL,
            )
            for line in out.split("\n"):
                if "Chipset Model" in line:
                    return line.split(":")[1].strip()
        elif system != "Windows":
            out = _check_output(
                "lspci | grep -i vga",
                shell=True,
                text=True,
                stderr=subprocess.DEVNULL,
            )
            return out.strip().split(": ")[-1]
    except Exception:
        pass
    return "Unknown"
 
 
def print_header(title):
    if not SHOW_HEADERS:
        return
    print("\n" + "=" * 50)
    print(f" {title}")
    print("=" * 50)
 
 
def show_system_and_board():
    system = ps_json(
        "Get-CimInstance Win32_ComputerSystem | Select Manufacturer,Model"
    )
    board = ps_json(
        "Get-CimInstance Win32_BaseBoard | Select Manufacturer,Product,Version"
    )
    bios = ps_json(
        "Get-CimInstance Win32_BIOS | Select Manufacturer,SMBIOSBIOSVersion,"
        "@{n='Date';e={$_.ReleaseDate.ToString('yyyy-MM-dd')}}"
    )
 
    print_header("Motherboard & BIOS")
    if system:
        s = system[0]
        print(f"System Maker      : {na(s.get('Manufacturer'))}")
        print(f"System Model      : {na(s.get('Model'))}")
    if board:
        b = board[0]
        print(f"Board Maker       : {na(b.get('Manufacturer'))}")
        print(f"Board Model       : {na(b.get('Product'))}")
        print(f"Board Version     : {na(b.get('Version'))}")
    if bios:
        x = bios[0]
        print(f"BIOS Vendor       : {na(x.get('Manufacturer'))}")
        print(f"BIOS Version      : {na(x.get('SMBIOSBIOSVersion'))}")
        print(f"BIOS Date         : {na(x.get('Date'))}")
    if not (system or board or bios):
        print("Not available")
 
 
def show_cpu_extra():
    cpu = ps_json(
        "Get-CimInstance Win32_Processor | Select SocketDesignation,"
        "L2CacheSize,L3CacheSize,MaxClockSpeed"
    )
    if not cpu:
        return
    c = cpu[0]
    print(f"Socket            : {na(c.get('SocketDesignation'))}")
    l2 = c.get("L2CacheSize")
    l3 = c.get("L3CacheSize")
    if l2:
        print(f"L2 Cache          : {get_size(l2 * 1024)}")
    if l3:
        print(f"L3 Cache          : {get_size(l3 * 1024)}")
    if c.get("MaxClockSpeed"):
        print(f"Rated Speed       : {c['MaxClockSpeed']} MHz")
 
 
def ram_form_label(memory_type, form_factor, type_detail):
    if memory_type in (27, 28, 29, 30, 35):
        return "LPDDR (soldered on board)"
    detail = type_detail if isinstance(type_detail, int) else 0
    if form_factor == 12:
        return "SO-DIMM"
    if form_factor == 8:
        if detail & 32768:
            return "LRDIMM"
        if detail & 8192:
            return "RDIMM"
        if detail & 16384:
            return "UDIMM"
        return "DIMM"
    names = {7: "SIMM", 11: "RIMM", 13: "SRIMM"}
    if form_factor in names:
        return names[form_factor]
    return f"Unknown (code {form_factor})" if form_factor is not None else "N/A"
 
 
def show_ram_modules():
    modules = ps_json(
        "Get-CimInstance Win32_PhysicalMemory | Select DeviceLocator,BankLabel,"
        "Manufacturer,PartNumber,Capacity,Speed,ConfiguredClockSpeed,"
        "SMBIOSMemoryType,FormFactor,TypeDetail"
    )
    arrays = ps_json("Get-CimInstance Win32_PhysicalMemoryArray | Select MemoryDevices")
    total_slots = sum(a.get("MemoryDevices") or 0 for a in arrays)
 
    if total_slots:
        print(f"Slots Used        : {len(modules)} of {total_slots}")
    labels = [
        ram_form_label(m.get("SMBIOSMemoryType"), m.get("FormFactor"), m.get("TypeDetail"))
        for m in modules
    ]
    for i, m in enumerate(modules, start=1):
        ram_type = RAM_TYPES.get(m.get("SMBIOSMemoryType"), "Unknown")
        capacity = get_size(m["Capacity"]) if m.get("Capacity") else "N/A"
        speed = m.get("ConfiguredClockSpeed") or m.get("Speed")
        speed_text = f"{speed} MHz" if speed else "N/A"
        slot = na(m.get("DeviceLocator"))
        if slot == "N/A":
            slot = na(m.get("BankLabel"))
        form = labels[i - 1]
        print(f"\nModule {i} ({slot})")
        print(f"  Type        : {ram_type}")
        print(f"  Form Factor : {form}")
        print(f"  Size        : {capacity}")
        print(f"  Speed       : {speed_text}")
        print(f"  Maker       : {na(m.get('Manufacturer'))}")
        print(f"  Part Number : {na(m.get('PartNumber'))}")
 
 
def show_gpu_details():
    gpus = ps_json(
        "Get-CimInstance Win32_VideoController | Select Name,AdapterRAM,DriverVersion"
    )
    for i, g in enumerate(gpus, start=1):
        print(f"\nGPU {i}")
        print(f"  Name        : {na(g.get('Name'))}")
        vram = g.get("AdapterRAM")
        if vram and vram > 0:
            print(f"  VRAM        : {get_size(vram)} (may be inaccurate)")
        print(f"  Driver      : {na(g.get('DriverVersion'))}")
    if not gpus:
        print("Not available")
 
 
def show_physical_disks():
    disks = ps_json(
        "Get-PhysicalDisk | Select FriendlyName,"
        "@{n='MediaType';e={\"$($_.MediaType)\"}},"
        "@{n='BusType';e={\"$($_.BusType)\"}},"
        "@{n='HealthStatus';e={\"$($_.HealthStatus)\"}},Size"
    )
    if not disks:
        return
    print("Physical Disks")
    for i, d in enumerate(disks, start=1):
        size = get_size_both(d["Size"]) if d.get("Size") else "N/A"
        media = lookup(DISK_MEDIA, d.get("MediaType"))
        bus = lookup(DISK_BUS, d.get("BusType"))
        health = lookup(DISK_HEALTH, d.get("HealthStatus"))
        print(f"\n  Disk {i}: {na(d.get('FriendlyName'))}")
        print(f"    Type        : {media} ({bus})")
        print(f"    Size        : {size}")
        print(f"    Health      : {health}")
    print("\nPartitions")
 
 
SMBIOS_CMD = (
    "$d=(Get-CimInstance -Namespace root/wmi -ClassName MSSmbios_RawSMBiosTables).SMBiosData; "
    "if ($d) { [BitConverter]::ToString($d) -replace '-','' }"
)
 
GENERIC_WORDS = (
    "not specified", "unknown", "to be filled", "default string",
    "o.e.m", "none", "n/a", "undefined",
)
NOISE_WORDS = {"cpu", "processor", "nvme", "scsi", "disk", "device", "ata", "usb"}
 
PCI_VENDORS = {
    "10DE": "NVIDIA",
    "1002": "AMD",
    "1022": "AMD",
    "8086": "Intel",
    "1414": "Microsoft",
    "80EE": "VirtualBox",
    "15AD": "VMware",
}
NAME_VENDORS = [
    (r"\b(nvidia|geforce|quadro|rtx|gtx)\b", "NVIDIA"),
    (r"\b(amd|radeon|ati)\b", "AMD"),
    (r"\b(intel|iris|uhd)\b", "Intel"),
    (r"\bvirtualbox\b", "VirtualBox"),
    (r"\bvmware\b", "VMware"),
    (r"\bmicrosoft\b", "Microsoft"),
]
 
 
def is_generic(text):
    t = (text or "").strip().lower()
    return t == "" or any(w in t for w in GENERIC_WORDS)
 
 
def name_tokens(text):
    t = str(text).lower()
    t = re.sub(r"\((r|tm|c)\)", " ", t)
    t = re.sub(r"@.*$", " ", t)
    t = re.sub(r"\b\d+(\.\d+)?\s*ghz\b", " ", t)
    t = re.sub(r"\b\d+-core\b", " ", t)
    t = re.sub(r"[^a-z0-9\-]+", " ", t)
    return {w for w in t.split() if w not in NOISE_WORDS}
 
 
def names_consistent(a, b, min_tokens=2):
    ta, tb = name_tokens(a), name_tokens(b)
    if len(ta) < min_tokens or len(tb) < min_tokens:
        return None
    return ta <= tb or tb <= ta
 
 
def parse_smbios(data):
    tables = []
    i = 0
    n = len(data)
    while i + 4 <= n:
        table_type = data[i]
        length = data[i + 1]
        if length < 4:
            break
        formatted = data[i:i + length]
        start = i + length
        j = start
        while j + 1 < n and not (data[j] == 0 and data[j + 1] == 0):
            j += 1
        raw = data[start:j]
        strings = [s.decode("utf-8", "replace").strip() for s in raw.split(b"\x00")] if raw else []
        tables.append((table_type, formatted, strings))
        i = j + 2
        if table_type == 127:
            break
    return tables
 
 
def smbios_string(formatted, strings, offset):
    if offset >= len(formatted):
        return ""
    idx = formatted[offset]
    if idx == 0 or idx > len(strings):
        return ""
    return strings[idx - 1]
 
 
def smbios_memory_mb(formatted):
    if len(formatted) < 14:
        return 0
    size = int.from_bytes(formatted[12:14], "little")
    if size in (0, 0xFFFF):
        return 0
    if size == 0x7FFF:
        if len(formatted) >= 0x20:
            return int.from_bytes(formatted[0x1C:0x20], "little") & 0x7FFFFFFF
        return 0
    if size & 0x8000:
        return (size & 0x7FFF) // 1024
    return size
 
 
def read_smbios():
    try:
        lines = run_powershell(SMBIOS_CMD)
        if not lines:
            return None
        return parse_smbios(bytes.fromhex(lines[0]))
    except Exception:
        return None
 
 
def check_cpu(tables, win_name):
    if tables is None:
        return "UNVERIFIED", ["BIOS data not readable (try running as Administrator)"]
    bios_name = ""
    for table_type, formatted, strings in tables:
        if table_type == 4:
            value = smbios_string(formatted, strings, 0x10)
            if value:
                bios_name = value
                break
    lines = [f"BIOS    : {bios_name or 'N/A'}", f"Windows : {win_name or 'N/A'}"]
    if is_generic(bios_name) or is_generic(win_name):
        return "UNVERIFIED", lines + ["One source gave no usable CPU name"]
    result = names_consistent(bios_name, win_name, 2)
    if result is None:
        return "UNVERIFIED", lines + ["Names too short to compare"]
    return ("OK" if result else "SUSPICIOUS"), lines
 
 
def check_ram(tables, win_modules):
    if tables is None:
        return "UNVERIFIED", ["BIOS data not readable (try running as Administrator)"]
    bios_mods = []
    for table_type, formatted, strings in tables:
        if table_type != 17:
            continue
        mb = smbios_memory_mb(formatted)
        if not mb:
            continue
        bios_mods.append({
            "maker": smbios_string(formatted, strings, 0x17),
            "part": smbios_string(formatted, strings, 0x1A),
            "mb": mb,
        })
    win_mods = []
    for m in win_modules:
        if not m.get("Capacity"):
            continue
        win_mods.append({
            "maker": str(m.get("Manufacturer") or "").strip(),
            "part": str(m.get("PartNumber") or "").strip(),
            "mb": int(m["Capacity"]) // (1024 * 1024),
        })
 
    def key(m):
        return (m["part"].strip().lower(), m["mb"])
 
    lines = []
    for label, mods in (("BIOS   ", bios_mods), ("Windows", win_mods)):
        for m in mods:
            lines.append(f"{label} : {m['mb']} MiB  {m['part'] or 'N/A'}  ({m['maker'] or 'N/A'})")
    if not bios_mods or not win_mods:
        return "UNVERIFIED", lines + ["One source reported no memory modules"]
    if len(bios_mods) != len(win_mods):
        return "SUSPICIOUS", lines + [
            f"BIOS reports {len(bios_mods)} module(s), Windows reports {len(win_mods)}"
        ]
    if sorted(map(key, bios_mods)) != sorted(map(key, win_mods)):
        return "SUSPICIOUS", lines + ["Part number or size differs between BIOS and Windows"]
    return "OK", lines
 
 
def check_disk(physical, drives):
    if not physical or not drives:
        return "UNVERIFIED", ["Windows did not return disk names from both sources"]
    by_index = {str(d.get("Index")): str(d.get("Model") or "").strip() for d in drives}
    lines, bad, checked = [], False, 0
    for p in physical:
        friendly = str(p.get("FriendlyName") or "").strip()
        model = by_index.get(str(p.get("DeviceId")), "")
        lines.append(f"Storage API : {friendly or 'N/A'}")
        lines.append(f"Disk driver : {model or 'N/A'}")
        if is_generic(friendly) or is_generic(model):
            lines.append("  (one source gave no usable name)")
            continue
        result = names_consistent(friendly, model, 1)
        if result is None:
            lines.append("  (name too short to compare)")
            continue
        checked += 1
        if not result:
            bad = True
            lines.append("  MISMATCH between the two names")
    status = "SUSPICIOUS" if bad else ("OK" if checked else "UNVERIFIED")
    return status, lines
 
 
def name_vendor_of(name):
    for pattern, vendor in NAME_VENDORS:
        if re.search(pattern, name, re.I):
            return vendor
    return None
 
 
def check_gpu(gpus):
    if not gpus:
        return "UNVERIFIED", ["Windows returned no GPU information"]
    lines, bad, checked = [], False, 0
    for g in gpus:
        name = str(g.get("Name") or "").strip()
        pnp = str(g.get("PNPDeviceID") or "")
        m = re.search(r"VEN_([0-9A-F]{4})&DEV_([0-9A-F]{4})", pnp, re.I)
        if not m:
            lines.append(f"{name or 'N/A'}: not a PCI device, cannot verify")
            continue
        ven, dev = m.group(1).upper(), m.group(2).upper()
        pci_vendor = PCI_VENDORS.get(ven)
        lines.append(f"Windows name : {name or 'N/A'}")
        lines.append(f"PCI hardware : VEN_{ven} DEV_{dev} ({pci_vendor or 'unknown vendor'})")
        if re.search(r"basic (display|render)", name, re.I):
            lines.append("  (no GPU driver installed yet, name is generic)")
            continue
        name_vendor = name_vendor_of(name)
        if not pci_vendor or not name_vendor:
            continue
        checked += 1
        if pci_vendor != name_vendor:
            bad = True
            lines.append(f"  MISMATCH: name says {name_vendor}, hardware ID says {pci_vendor}")
    status = "SUSPICIOUS" if bad else ("OK" if checked else "UNVERIFIED")
    return status, lines
 
 
def show_name_check():
    print_header("Hardware Name Check")
    if platform.system() != "Windows":
        print("Windows only")
        return
 
    tables = read_smbios()
    cpu_rows = ps_json("Get-CimInstance Win32_Processor | Select Name")
    win_cpu = str(cpu_rows[0].get("Name") or "").strip() if cpu_rows else ""
    ram_rows = ps_json(
        "Get-CimInstance Win32_PhysicalMemory | Select Manufacturer,PartNumber,Capacity"
    )
    physical = ps_json("Get-PhysicalDisk | Select DeviceId,FriendlyName")
    drives = ps_json("Get-CimInstance Win32_DiskDrive | Select Index,Model")
    gpus = ps_json("Get-CimInstance Win32_VideoController | Select Name,PNPDeviceID")
 
    results = {
        "CPU": check_cpu(tables, win_cpu),
        "RAM": check_ram(tables, ram_rows),
        "Disk": check_disk(physical, drives),
        "GPU": check_gpu(gpus),
    }
    for label, (status, lines) in results.items():
        print(f"\n{label:<5}: {status}")
        for line in lines:
            print(f"       {line}")
 
    suspicious = [label for label, (status, _) in results.items() if status == "SUSPICIOUS"]
    unverified = [label for label, (status, _) in results.items() if status == "UNVERIFIED"]
    print()
    if suspicious:
        print("suspic hardware name: " + ", ".join(suspicious))
    else:
        print("No mismatch found in the names that could be compared.")
    if unverified:
        print("Could not verify: " + ", ".join(unverified))
 
 
VIDPID_RE = re.compile(r"VID_([0-9A-F]{4})&PID_([0-9A-F]{4})", re.I)
HUB_WORDS = ("hub", "host controller", "root")
 
USB_CMD = (
    "Get-PnpDevice -PresentOnly | "
    "Where-Object { $_.InstanceId -match '^USB\\\\VID_[0-9A-F]{4}&PID_[0-9A-F]{4}\\\\' } | "
    "Select-Object FriendlyName,InstanceId,"
    "@{n='Product';e={(Get-PnpDeviceProperty -InstanceId $_.InstanceId "
    "-KeyName DEVPKEY_Device_BusReportedDeviceDesc -ErrorAction SilentlyContinue).Data}}"
)
HID_CMD = (
    "Get-PnpDevice -PresentOnly -Class Keyboard,Mouse | "
    "Select-Object Class,FriendlyName,InstanceId"
)
AUDIO_CMD = (
    "Get-PnpDevice -PresentOnly -Class AudioEndpoint | "
    "Where-Object { $_.Status -eq 'OK' } | Select-Object FriendlyName"
)
BT_CMD = (
    "Get-PnpDevice -PresentOnly | "
    "Where-Object { $_.InstanceId -match '^BTH(ENUM|LE)\\\\DEV_' } | "
    "Select-Object FriendlyName"
)
 
 
def usb_key(instance_id):
    m = VIDPID_RE.search(str(instance_id or ""))
    if not m:
        return None
    return (m.group(1).upper(), m.group(2).upper())
 
 
def unique_names(rows):
    seen, names = set(), []
    for r in rows:
        name = str(r.get("FriendlyName") or "").strip()
        if name and name.lower() not in seen:
            seen.add(name.lower())
            names.append(name)
    return names
 
 
def collect_accessories(usb_rows, hid_rows, audio_rows, bt_rows):
    usb = {}
    for r in usb_rows:
        key = usb_key(r.get("InstanceId"))
        if not key or key in usb:
            continue
        product = str(r.get("Product") or "").strip()
        friendly = str(r.get("FriendlyName") or "").strip()
        usb[key] = product or friendly or "USB device"
 
    inputs, seen, used, hidden = [], set(), set(), 0
    for r in hid_rows:
        instance_id = str(r.get("InstanceId") or "")
        upper = instance_id.upper()
        kind = "Keyboard" if str(r.get("Class")) == "Keyboard" else "Mouse"
        friendly = str(r.get("FriendlyName") or "").strip()
        key = usb_key(instance_id)
        if "BTH" in upper or "00001124" in upper:
            conn, name, id_text = "Bluetooth", friendly, ""
        elif upper.startswith("HID\\") and key:
            conn, name = "USB", usb.get(key) or friendly
            id_text = f"{key[0]}:{key[1]}"
            used.add(key)
        else:
            hidden += 1
            continue
        item = (kind, name, conn, id_text)
        if item not in seen:
            seen.add(item)
            inputs.append(item)
 
    others = []
    for key, name in sorted(usb.items(), key=lambda kv: kv[1].lower()):
        if key in used:
            continue
        if any(w in name.lower() for w in HUB_WORDS):
            continue
        others.append((name, f"{key[0]}:{key[1]}"))
 
    return {
        "inputs": inputs,
        "hidden_inputs": hidden,
        "audio": unique_names(audio_rows),
        "bluetooth": unique_names(bt_rows),
        "other_usb": others,
    }
 
 
def show_accessories():
    print_header("Accessories")
    if platform.system() != "Windows":
        print("Windows only")
        return
 
    data = collect_accessories(
        ps_json(USB_CMD), ps_json(HID_CMD), ps_json(AUDIO_CMD), ps_json(BT_CMD)
    )
 
    print("Keyboards & Mice (USB / Bluetooth)")
    if data["inputs"]:
        for kind, name, conn, id_text in sorted(data["inputs"]):
            extra = f", ID {id_text}" if id_text else ""
            print(f"  {kind:<9}: {name} ({conn}{extra})")
    else:
        print("  None detected")
    if data["hidden_inputs"]:
        print(f"  ({data['hidden_inputs']} built-in or virtual input device(s) not listed)")
 
    print("\nAudio devices (active)")
    if data["audio"]:
        for name in data["audio"]:
            print(f"  {name}")
    else:
        print("  None detected")
 
    print("\nBluetooth paired devices (paired, not necessarily connected)")
    if data["bluetooth"]:
        if SHOW_BLUETOOTH_NAMES:
            for name in data["bluetooth"]:
                print(f"  {name}")
        else:
            print(f"  {len(data['bluetooth'])} device(s) (names hidden)")
    else:
        print("  None detected")
 
    print("\nOther USB devices")
    if data["other_usb"]:
        for name, id_text in data["other_usb"]:
            print(f"  {name} (ID {id_text})")
    else:
        print("  None detected")
 
 
def get_output_dir():
    if getattr(sys, "frozen", False):
        return os.path.dirname(sys.executable)
    return os.path.dirname(os.path.abspath(__file__))
 
 
WINDOWS_RESERVED = {
    "CON", "PRN", "AUX", "NUL",
    *(f"COM{i}" for i in range(1, 10)),
    *(f"LPT{i}" for i in range(1, 10)),
}
 
 
def safe_folder_name(text):
    name = re.sub(r'[<>:"/\\|?*\x00-\x1f]', "_", str(text))
    name = re.sub(r"\s+", " ", name).strip(" .")
    name = name[:80].strip(" .")
    if not name:
        return "UnknownBoard"
    if name.split(".")[0].upper() in WINDOWS_RESERVED:
        name = "_" + name
    return name
 
 
def get_board_folder_name():
    system = platform.system()
    maker, product = "", ""
    try:
        if system == "Windows":
            board = ps_json("Get-CimInstance Win32_BaseBoard | Select Manufacturer,Product")
            if board:
                maker = str(board[0].get("Manufacturer") or "").strip()
                product = str(board[0].get("Product") or "").strip()
            if is_generic(product):
                info = ps_json("Get-CimInstance Win32_ComputerSystem | Select Manufacturer,Model")
                if info:
                    maker = str(info[0].get("Manufacturer") or "").strip()
                    product = str(info[0].get("Model") or "").strip()
        elif system == "Linux":
            base = "/sys/devices/virtual/dmi/id/"
            with open(base + "board_vendor") as f:
                maker = f.read().strip()
            with open(base + "board_name") as f:
                product = f.read().strip()
        elif system == "Darwin":
            product = _check_output(
                ["sysctl", "-n", "hw.model"], text=True, stderr=subprocess.DEVNULL
            ).strip()
    except Exception:
        pass
    if is_generic(product):
        return "UnknownBoard"
    if is_generic(maker):
        return safe_folder_name(product)
    return safe_folder_name(f"{maker} {product}")
 
 
def save_report(text):
    stamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    filename = f"PcChecker_{stamp}.txt"
    folder = os.path.join(get_output_dir(), get_board_folder_name())
    path = os.path.join(folder, filename)
    try:
        os.makedirs(folder, exist_ok=True)
        with open(path, "w", encoding="utf-8") as f:
            f.write(text)
        return f"Report saved to: {path}"
    except Exception as e:
        return f"Could not save report: {e}"
 
 
NOTICE_LINES = (
    "All results above may differ from the actual hardware.",
    "Always verify with the physical hardware as well.",
)
NOTICE_SHORT = (
    "All results may differ from the actual hardware. "
    "Always verify with the physical hardware as well."
)
 
 
def print_disclaimer():
    print_header("Notice")
    for line in NOTICE_LINES:
        print(line)
 
 
def section_system():
    print_header("System Information")
    uname = platform.uname()
    print(f"Report Time       : {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print(f"Operating System  : {uname.system} {uname.release}")
    print(f"Version           : {uname.version}")
    print(f"Architecture      : {uname.machine}")
    print(f"Python            : {platform.python_version()}")
 
 
def section_board():
    if platform.system() == "Windows":
        show_system_and_board()
    else:
        print_header("Motherboard & BIOS")
        print("Windows only")
 
 
def section_cpu():
    print_header("CPU")
    print(f"Name              : {get_cpu_name()}")
    if platform.system() == "Windows":
        show_cpu_extra()
    print(f"Physical Cores    : {psutil.cpu_count(logical=False)}")
    print(f"Threads           : {psutil.cpu_count(logical=True)}")
    freq = psutil.cpu_freq()
    if freq:
        print(f"Max Frequency     : {freq.max:.0f} MHz")
        print(f"Current Frequency : {freq.current:.0f} MHz")
    print(f"CPU Usage         : {psutil.cpu_percent(interval=1)}%")
 
 
def section_memory():
    print_header("Memory (RAM)")
    mem = psutil.virtual_memory()
    print(f"Total             : {get_size(mem.total)}")
    print(f"Used              : {get_size(mem.used)} ({mem.percent}%)")
    print(f"Available         : {get_size(mem.available)}")
    swap = psutil.swap_memory()
    print(f"Swap Total        : {get_size(swap.total)}")
    if platform.system() == "Windows":
        show_ram_modules()
 
 
def section_gpu():
    print_header("Graphics (GPU)")
    if platform.system() == "Windows":
        show_gpu_details()
    else:
        print(f"Name              : {get_gpu_info()}")
 
 
def section_disk():
    print_header("Disk")
    if platform.system() == "Windows":
        show_physical_disks()
    for part in psutil.disk_partitions():
        try:
            usage = psutil.disk_usage(part.mountpoint)
        except (PermissionError, OSError):
            continue
        print(f"\nDrive {part.device} ({part.fstype})")
        print(f"  Mount Point : {part.mountpoint}")
        print(f"  Total       : {get_size_both(usage.total)}")
        print(f"  Used        : {get_size_both(usage.used)} ({usage.percent}%)")
        print(f"  Free        : {get_size_both(usage.free)}")
 
 
def section_battery():
    battery = psutil.sensors_battery()
    if battery:
        print_header("Battery")
        print(f"Level             : {battery.percent}%")
        print(f"Charging          : {'Yes' if battery.power_plugged else 'No'}")
 
 
SECTIONS = [
    ("System", "System Information", section_system, False),
    ("Motherboard", "Motherboard & BIOS", section_board, True),
    ("CPU", "CPU", section_cpu, False),
    ("Memory", "Memory (RAM)", section_memory, False),
    ("GPU", "Graphics (GPU)", section_gpu, False),
    ("Disk", "Disk", section_disk, False),
    ("Battery", "Battery", section_battery, False),
    ("Accessories", "Accessories", show_accessories, True),
    ("Name Check", "Hardware Name Check", show_name_check, True),
]
 
 
def main():
    is_windows = platform.system() == "Windows"
    for tab, header, func, windows_only in SECTIONS:
        if windows_only and not is_windows:
            continue
        func()
    print_disclaimer()
 
 
def collect_sections():
    global SHOW_HEADERS
    is_windows = platform.system() == "Windows"
    results = []
    SHOW_HEADERS = False
    try:
        for tab, header, func, windows_only in SECTIONS:
            if windows_only and not is_windows:
                results.append((tab, header, "Windows only"))
                continue
            buffer = io.StringIO()
            try:
                with contextlib.redirect_stdout(buffer):
                    func()
                text = buffer.getvalue().strip("\n")
            except Exception as e:
                text = f"Error while reading this section: {e}"
            results.append((tab, header, text))
    finally:
        SHOW_HEADERS = True
    return results
 
 
def build_report(results):
    bar = "=" * 50
    blocks = []
    for tab, header, text in results:
        if text:
            blocks.append(f"\n{bar}\n {header}\n{bar}\n{text}")
    blocks.append(f"\n{bar}\n Notice\n{bar}\n" + "\n".join(NOTICE_LINES))
    return "\n".join(blocks) + "\n"
 
 
def run_console():
    buffer = io.StringIO()
    sys.stdout = Tee(sys.__stdout__, buffer)
    try:
        main()
    finally:
        sys.stdout = sys.__stdout__
    if SAVE_REPORT:
        print("\n" + save_report(buffer.getvalue()))
    input("\nPress Enter to exit...")
 
 
def run_gui():
    try:
        import queue
        import threading
        import tkinter as tk
        from tkinter import ttk
    except Exception:
        print("tkinter is not available, running in console mode instead.")
        run_console()
        return
 
    try:
        import ctypes
        ctypes.windll.shcore.SetProcessDpiAwareness(1)
    except Exception:
        pass
 
    root = tk.Tk()
    root.title("Pc Checker")
    root.geometry("920x640")
    root.minsize(640, 400)
 
    top = ttk.Frame(root, padding=(8, 8, 8, 0))
    top.pack(fill="x")
    refresh_btn = ttk.Button(top, text="Refresh")
    refresh_btn.pack(side="left")
    save_btn = ttk.Button(top, text="Save report")
    save_btn.pack(side="left", padx=(6, 0))
    status = tk.StringVar(value="Checking...")
    ttk.Label(top, textvariable=status).pack(side="left", padx=12)
 
    notebook = ttk.Notebook(root)
    notebook.pack(fill="both", expand=True, padx=8, pady=8)
 
    widgets = {}
    for tab, header, func, windows_only in SECTIONS:
        frame = ttk.Frame(notebook)
        box = tk.Text(
            frame, wrap="none", font=("Consolas", 10), state="disabled",
            borderwidth=0, padx=8, pady=6,
        )
        ybar = ttk.Scrollbar(frame, orient="vertical", command=box.yview)
        xbar = ttk.Scrollbar(frame, orient="horizontal", command=box.xview)
        box.configure(yscrollcommand=ybar.set, xscrollcommand=xbar.set)
        box.grid(row=0, column=0, sticky="nsew")
        ybar.grid(row=0, column=1, sticky="ns")
        xbar.grid(row=1, column=0, sticky="ew")
        frame.rowconfigure(0, weight=1)
        frame.columnconfigure(0, weight=1)
        notebook.add(frame, text=tab)
        widgets[tab] = box
 
    ttk.Label(root, text=NOTICE_SHORT, padding=(8, 0, 8, 8), wraplength=880).pack(fill="x")
 
    results_queue = queue.Queue()
    state = {"report": "", "busy": False, "first": True}
 
    def set_text(box, text):
        box.configure(state="normal")
        box.delete("1.0", "end")
        box.insert("1.0", text)
        box.configure(state="disabled")
 
    def set_busy(busy):
        state["busy"] = busy
        mode = ["disabled"] if busy else ["!disabled"]
        refresh_btn.state(mode)
        save_btn.state(mode)
 
    def poll():
        try:
            result = results_queue.get_nowait()
        except queue.Empty:
            root.after(150, poll)
            return
        set_busy(False)
        if isinstance(result, Exception):
            status.set(f"Error: {result}")
            return
        for tab, header, text in result:
            empty = "No battery detected." if tab == "Battery" else "No data."
            set_text(widgets[tab], text or empty)
        state["report"] = build_report(result)
        if state["first"] and GUI_AUTO_SAVE:
            status.set(save_report(state["report"]))
        else:
            status.set("Done. Click Save report to keep a copy.")
        state["first"] = False
 
    def worker():
        try:
            results_queue.put(collect_sections())
        except Exception as e:
            results_queue.put(e)
 
    def start():
        if state["busy"]:
            return
        set_busy(True)
        status.set("Checking... this can take a few seconds")
        for box in widgets.values():
            set_text(box, "Loading...")
        threading.Thread(target=worker, daemon=True).start()
        root.after(150, poll)
 
    def save_now():
        if state["report"]:
            status.set(save_report(state["report"]))
 
    refresh_btn.configure(command=start)
    save_btn.configure(command=save_now)
    start()
    root.mainloop()
 
 
if __name__ == "__main__":
    if "--console" in sys.argv:
        run_console()
    else:
        run_gui()
 














