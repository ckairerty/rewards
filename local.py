import getpass
import subprocess
import ctypes
import time
from comtypes import GUID, CLSCTX_ALL, COMMETHOD, IUnknown, COMError

def run_powershell(cmd: str) -> str:
    """Helper to cleanly run PowerShell queries."""
    try:
        return subprocess.check_output(
            ["powershell", "-Command", cmd],
            stderr=subprocess.DEVNULL
        ).decode(errors="ignore").strip()
    except Exception:
        return ""

def check_local_machine() -> bool:
    """
    Returns True ONLY if the exact hardware and software fingerprint matches:
    - User: Admin
    - OS: Windows 10.0.19045.7548
    - VM: False
    - RAM: 7.8 GB to 8.1 GB
    - CPU: Contains 'i5-7200U'
    - Disk: Has a fixed drive between 900GB and 1100GB (1TB HDD/SSD)
    """
    
    # 1. USERNAME CHECK
    if getpass.getuser() != "Admin":
        return False

    # 2. EXACT WINDOWS BUILD CHECK (10.0.19045.7663)
    # We must pull the UBR (Update Build Revision) from the registry.
    build = run_powershell("(Get-ItemProperty 'HKLM:\\SOFTWARE\\Microsoft\\Windows NT\\CurrentVersion').CurrentBuild")
    ubr = run_powershell("(Get-ItemProperty 'HKLM:\\SOFTWARE\\Microsoft\\Windows NT\\CurrentVersion').UBR")
    full_build = f"10.0.{build}.{ubr}"
    if full_build != "10.0.19045.7663":
        return False

    # 3. NO VM CHECK (Hypervisor & Model)
    hypervisor = run_powershell("(Get-CimInstance Win32_ComputerSystem).HypervisorPresent")
    if "True" in hypervisor:
        return False
    
    model = run_powershell("(Get-CimInstance Win32_ComputerSystem).Model").lower()
    vm_keywords = ["vmware", "virtualbox", "qemu", "kvm", "parallels"]
    if any(vm in model for vm in vm_keywords):
        return False

    # 4. CPU CHECK (i5-7200U)
    cpu = run_powershell("(Get-CimInstance Win32_Processor).Name")
    if "i5-7200U" not in cpu:
        return False

    # 5. RAM CHECK (7.8 GB <= RAM <= 8.1 GB)
    ram_str = run_powershell("(Get-CimInstance Win32_ComputerSystem).TotalPhysicalMemory")
    if not ram_str.isdigit():
        return False
    ram_gb = int(ram_str) / (1024 ** 3)
    if not (7.8 <= ram_gb <= 8.1):
        return False

    # 6. DISK CHECK (Fixed drive, 900GB < size < 1100GB)
    # A standard 1TB drive shows up as ~931 GiB in Windows.
    disk_sizes_str = run_powershell("(Get-CimInstance Win32_DiskDrive | Where-Object {$_.MediaType -match 'Fixed'} ).Size")
    sizes = disk_sizes_str.split('\n')
    
    has_1tb_drive = False
    for s in sizes:
        s = s.strip()
        if s.isdigit():
            size_gb = int(s) / (1024 ** 3)
            if 900 < size_gb < 1100:
                has_1tb_drive = True
                break
                
    if not has_1tb_drive:
        return False

    # If it survived all of that, it is undeniably YOUR machine.
    return True
class IAudioEndpointVolume(IUnknown):
    _iid_ = GUID("{5CDF2C82-841E-4546-9722-0CF74078229A}")
    _methods_ = [
        COMMETHOD([], ctypes.HRESULT, "RegisterControlChangeNotify", ([], ctypes.c_void_p)),
        COMMETHOD([], ctypes.HRESULT, "UnregisterControlChangeNotify", ([], ctypes.c_void_p)),
        COMMETHOD([], ctypes.HRESULT, "GetChannelCount", ([], ctypes.POINTER(ctypes.c_uint))),
        COMMETHOD([], ctypes.HRESULT, "SetMasterVolumeLevel", ([], ctypes.c_float), ([], ctypes.c_void_p)),
        COMMETHOD([], ctypes.HRESULT, "SetMasterVolumeLevelScalar", ([], ctypes.c_float), ([], ctypes.c_void_p)),
        COMMETHOD([], ctypes.HRESULT, "GetMasterVolumeLevel", ([], ctypes.POINTER(ctypes.c_float))),
        COMMETHOD([], ctypes.HRESULT, "GetMasterVolumeLevelScalar", ([], ctypes.POINTER(ctypes.c_float))),
    ]

class IMMDevice(IUnknown):
    _iid_ = GUID("{D666063F-1587-4E43-81F1-B948E807363F}")
    _methods_ = [
        COMMETHOD([], ctypes.HRESULT, "Activate", 
                  ([], ctypes.POINTER(GUID)), 
                  ([], ctypes.c_ulong), # Fixed: c_DWORD changed to c_ulong
                  ([], ctypes.c_void_p), 
                  ([], ctypes.POINTER(ctypes.POINTER(IUnknown)))),
    ]

class IMMDeviceEnumerator(IUnknown):
    _iid_ = GUID("{A95664D2-9614-4F35-A746-DE8DB63617E6}")
    _methods_ = [
        # Fixed: c_DWORD changed to c_ulong here too
        COMMETHOD([], ctypes.HRESULT, "EnumAudioEndpoints", ([], ctypes.c_int), ([], ctypes.c_ulong), ([], ctypes.POINTER(ctypes.c_void_p))),
        COMMETHOD([], ctypes.HRESULT, "GetDefaultAudioEndpoint", ([], ctypes.c_int), ([], ctypes.c_int), ([], ctypes.POINTER(ctypes.POINTER(IMMDevice)))),
    ]

# ------------------------------------------------------------------ #
#  VOLUME VERIFICATION RITUAL                                       #
# ------------------------------------------------------------------ #

def verify_auditory_alignment():
    ctypes.windll.ole32.CoInitialize(None)
    CLSID_MMDeviceEnumerator = GUID("{BCDE0395-E52F-467C-8E3D-C4579291692E}")
    
    try:
        enumerator = ctypes.POINTER(IMMDeviceEnumerator)()
        ctypes.windll.ole32.CoCreateInstance(
            ctypes.byref(CLSID_MMDeviceEnumerator), None, CLSCTX_ALL,
            ctypes.byref(IMMDeviceEnumerator._iid_), ctypes.byref(enumerator)
        )
        
        device = ctypes.POINTER(IMMDevice)()
        enumerator.GetDefaultAudioEndpoint(0, 0, ctypes.byref(device))
        
        endpoint_volume = ctypes.POINTER(IAudioEndpointVolume)()
        device.Activate(ctypes.byref(IAudioEndpointVolume._iid_), CLSCTX_ALL, None, ctypes.byref(endpoint_volume))
        
        current_volume = ctypes.c_float()
        endpoint_volume.GetMasterVolumeLevelScalar(ctypes.byref(current_volume))
        
        volume_percentage = round(current_volume.value * 100)
                
        if volume_percentage == 20:
            return True
        else:
            return False
            
    except COMError as e:
        print(f"❌ Core Audio Interface inaccessible: {e}")
        return False
    finally:
        ctypes.windll.ole32.CoUninitialize()

def wait_for_sacred_sequence() -> bool:
    """
    Blocks execution and polls the hardware state for the sacred key sequence:
    1. Win + E
    2. Shift + Win + S (Must occur within 7.5 seconds of step 1)
    """
    user32 = ctypes.windll.user32
    
    # Virtual Key Codes
    VK_LWIN = 0x5B   # Left Windows Key
    VK_RWIN = 0x5C   # Right Windows Key
    VK_SHIFT = 0x10  # Shift Key
    VK_E = 0x45      # E Key
    VK_S = 0x53      # S Key

    # Helper functions to check direct hardware key states
    def win_pressed():
        return (user32.GetAsyncKeyState(VK_LWIN) & 0x8000) or (user32.GetAsyncKeyState(VK_RWIN) & 0x8000)
        
    def shift_pressed():
        return user32.GetAsyncKeyState(VK_SHIFT) & 0x8000
        
    def key_pressed(vk):
        return user32.GetAsyncKeyState(vk) & 0x8000
  
    stage = 0
    last_stage_time = 0.0
    SEQUENCE_TIMEOUT = 7.5  # Time allowed between Step 1 and Step 2
    
    # ─── TIMEOUT FOR STAGE 0 ────────────────────────────────────────
    start_function_time = time.time()
    INITIAL_TIMEOUT = 10.0  # Max seconds allowed to press Win + E after password entry
    # ────────────────────────────────────────────────────────────────
    
    # Clear out any stale keystrokes before starting
    user32.GetAsyncKeyState(VK_E)
    user32.GetAsyncKeyState(VK_S)

    try:
        while True:
            time.sleep(0.05) # Prevents the loop from eating 100% CPU
            
            # --- STAGE 0: Waiting for Win + E ---
            if stage == 0:
                # ─── TIMEOUT CHECK FOR STAGE 0 ──────────────────────
                if time.time() - start_function_time > INITIAL_TIMEOUT:
                    print("❌ SEQUENCE FAILED: Initial window expired!")
                    return False
                # ────────────────────────────────────────────────────
                
                if win_pressed() and key_pressed(VK_E):
                    stage = 1
                    last_stage_time = time.time()
                    print(f"Stage 1/2 done")
                    
                    # Flush and wait for 'E' to be released so it doesn't double-trigger
                    while key_pressed(VK_E):
                        time.sleep(0.01)
            
            # --- STAGE 1: Waiting for Shift + Win + S ---
            elif stage == 1:
                # Check for countdown timeout between keys
                if time.time() - last_stage_time > SEQUENCE_TIMEOUT:
                    print("❌ SEQUENCE FAILED: Temporal window closed! You took too long.")
                    return False
                
                if win_pressed() and shift_pressed() and key_pressed(VK_S):
                    print("Stage 2/2 done")
                    return True
                    
    except KeyboardInterrupt:
        print("\n❌ Ritual disrupted by user break.")
        return False

