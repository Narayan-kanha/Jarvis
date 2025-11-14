# utils/system.py
import time
import psutil
import math
import socket
try:
    import pynvml; pynvml.nvmlInit(); PYNVML = True
except Exception:
    PYNVML = False

def get_gpu_status():
    if not PYNVML:
        return None, None
    try:
        handle = pynvml.nvmlDeviceGetHandleByIndex(0)
        temp = pynvml.nvmlDeviceGetTemperature(handle, pynvml.NVML_TEMPERATURE_GPU)
        util = pynvml.nvmlDeviceGetUtilizationRates(handle).gpu
        return int(temp), int(util)
    except Exception:
        return None, None

def gpu_monitor_thread(gui_confirm_callback=None, frequency: int = 5, temp_warn=75, temp_shut=80, util_warn=70, util_shut=85):
    while True:
        temp, util = get_gpu_status()
        if temp is not None:
            print("[GPU]", temp, "C,", util, "%")
            if temp >= temp_warn or util >= util_warn:
                # ask the user or just print
                if gui_confirm_callback:
                    gui_confirm_callback(f"Warning: GPU temp {temp}C util {util}%")
            if temp >= temp_shut or util >= util_shut:
                confirm = True
                if gui_confirm_callback:
                    confirm = gui_confirm_callback("GPU critical threshold reached. Shut down assistant?")
                if confirm:
                    print("[system] Shutting down assistant due to GPU")
                    import os; os._exit(0)
        time.sleep(frequency)

def convert_size(size_bytes: int) -> str:
    if size_bytes == 0:
        return "0B"
    size_name = ("B","KB","MB","GB","TB")
    i = int(math.floor(math.log(size_bytes, 1024)))
    p = math.pow(1024, i)
    s = round(size_bytes / p, 2)
    return f"{s} {size_name[i]}"

def system_stats() -> str:
    try:
        cpu = psutil.cpu_percent()
        batt = "N/A"
        try:
            b = psutil.sensors_battery()
            batt = b.percent if b is not None else "N/A"
        except Exception:
            batt = "N/A"
        used = convert_size(psutil.virtual_memory().used)
        total = convert_size(psutil.virtual_memory().total)
        return f"CPU: {cpu}%. RAM: {used} / {total}. Battery: {batt}%"
    except Exception:
        return "Could not fetch system stats."

def check_internet(timeout: float = 3.0) -> bool:
    try:
        socket.setdefaulttimeout(timeout)
        socket.socket(socket.AF_INET, socket.SOCK_STREAM).connect(("1.1.1.1", 53))
    except Exception:
        return False
    try:
        import requests
        requests.get("https://www.google.com", timeout=timeout)
        return True
    except Exception:
        return False
