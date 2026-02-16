#!/usr/bin/env python3

import pywemo
import sys
import time
import json
import subprocess
from pathlib import Path

from rich.panel import Panel
from rich.table import Table
from rich.prompt import Prompt, Confirm

import logConsole_base as base
from logConsole_base import console

# Initialize Logging from logConsole_base.py
logfile = base.initialize_logging(
    debug=True,
    enable_file=True,
    log_dir="logs",
    prefix="wemo_setup_"
)

log = base.get_logger("wemo_setup")

CONFIG_FILE = Path("config.json")
PROG_TITLE = "pyWeMo Network Configuration Utility"
VERSION = "4.5.69"

# ============================================================
# SYSTEM UTILITIES
# ============================================================

def fatal(message: str, code: int = 1):
    log.critical(message)
    sys.exit(code)

def run_command(cmd):
    log.debug(f"Exec: {cmd}")
    result = subprocess.run(cmd, capture_output=True, text=True, shell=True)
    return result.stdout

def enable_soap_logging():
    import requests.adapters
    old_send = requests.adapters.HTTPAdapter.send
    def new_send(self, request, **kwargs):
        log.debug(f"==> HTTP {request.method} {request.url}")
        response = old_send(self, request, **kwargs)
        log.debug(f"<== Status: {response.status_code}")
        return response
    requests.adapters.HTTPAdapter.send = new_send
    log.debug("Detailed SOAP/HTTP logging injected.")

def load_config():
    if not CONFIG_FILE.exists():
        return None
    try:
        with open(CONFIG_FILE, "r") as f:
            config = json.load(f)
        log.info("Configuration loaded from disk")
        return config
    except Exception as e:
        log.error(f"Failed to load config: {e}")
        return None
        
# ============================================================
# DISCOVERY - SCANNING
# ============================================================

def discover_devices_with_retry(retries=6, retry_delay=8):
    """
    Helper function - searches for wemo device in 'setup' mode.
    Since connected directly to device in AP mode basiclly can only be 1 device. (is not picky)
    """
    log.info("Starting device discovery scan")
    #console.print("[bold cyan]Starting device discovery scan...[/bold cyan]")
    console.rule(" Device Discovery Scan ")

    for attempt in range(1, retries + 1):
        log.debug(f"Discovery attempt {attempt}/{retries}...")
        time.sleep(1.2)
        try:
            devices = pywemo.discover_devices()
            if devices:
                target_device = None
                for d in devices:
                    if hasattr(d, 'setup'):
                        target_device = d
                        break

                if not target_device:
                    log.warning("No device with .setup(), using first.")
                    target_device = devices[0]

                device_info = {
                    "name": target_device.name,
                    "mac": getattr(target_device, 'mac', 'Unknown'),
                    "model": getattr(target_device, 'model_name', None) or getattr(target_device, 'device_type', 'Unknown'),
                    "host": target_device.host,
                    "serial": getattr(target_device, 'serialnumber', 'Unknown'),
                }

                log.info(f"Selected: {device_info['name']} ({device_info['model']}) | MAC: {device_info['mac']} ({device_info['host']})")

                return devices, device_info

        except Exception as e:
            log.warning(f"Discovery error attempt {attempt}: {e}")

        if attempt < retries:
            time.sleep(retry_delay)

    log.error("No devices after retries")
    return [], None

def discover_target_device(target_mac, retries=10, retry_delay=10):
    """
    Helper function - Scans the network for specifc wemo device using pywemo.discover_devices.
    Handles the WeMo MAC shift (e.g., B87C vs B87D) by checking the MAC prefix.
    Returns (list_of_devices, status_message) for unpacking.
    """
    log.info(f"Searching for device associated with MAC: {target_mac}")
    #console.print(f"[bold cyan] -- Scanning network for device (Target:[/bold cyan] [bold magenta]{target_mac}[/bold magenta][bold cyan])...[/bold cyan]")

    for attempt in range(1, retries + 1):
        log.debug(f"--- Discovery Attempt {attempt}/{retries} ---")
        
        # st=2 is short enough to be responsive but long enough for most Wemos (also stupid)
        found = pywemo.discover_devices() 
        
        if not found:
            log.debug("No Wemo devices responded to the SSDP broadcast on this attempt.")
        else:
            log.debug(f"Found {len(found)} Wemo device(s) on the network.")
            
            for d in found:
                this_mac = getattr(d, 'mac', None)
                this_name = getattr(d, 'name', 'Unknown')
                this_model = getattr(d, 'model_name', 'Unknown')
                
                log.debug(f"CHECKING DEVICE: Name='{this_name}' | Model='{this_model}' | MAC='{this_mac}' | Host='{d.host}'")
                
                if not this_mac:
                    log.debug(f"Skipping {this_name} - No MAC address attribute found.")
                    continue

                # 1. Check for exact match
                if this_mac.upper() == target_mac.upper():
                    log.info(f"MATCH FOUND (Exact MAC): {this_name} ({this_mac})")
                    return found, ""
                
                # 2. Check for Fuzzy Match (MAC shift)
                # We check if the first 11 characters match (the OUI and most of the NIC)
                if this_mac.upper()[:-1] == target_mac.upper()[:-1]:
                    log.info(f"MATCH FOUND (Fuzzy/Shifted MAC): Target {target_mac} matched with Device {this_mac}")
                    log.debug(f"Fuzzy match details: {this_name} at {d.host} looks like the target.")
                    return found, ""
                
                log.debug(f"Device {this_mac} is NOT a match for target {target_mac}.")

        if attempt < retries:
            log.debug(f"Target not found yet. Sleeping {retry_delay}s before next scan...")
            time.sleep(retry_delay)

    log.error(f"Fuzzy discovery failed. Could not find MAC prefix matching {target_mac[:-1]} after {retries} attempts.")
    return [], "Not found"

def check_device_ip_and_warn(device_info, config):
    """
    Helper funtion - check if devices IP is likely on the WeMo setup subnet
    Oddness can happen with some devices leaving a lingering AP SSID that can still be connected to after joining wifi.
    More oddness if windows decides to disconnect things for reasons and/or etc.
    Shows warning panel if unexpected things happen (ideally)
    Returns True if user wants to skip provisioning (end entire setup), False otherwise.
    """
    log.info("Checking device subnet")
    host_ip = device_info["host"]
    
    if host_ip.startswith("10.22.22."):
        return False  # normal setup IP → continue provisioning

    unexpected_subnet = ".".join(host_ip.split(".")[:3]) + "."
    target_ssid = config.get("ssid", "the target network")

    console.print(Panel(
        f"[bold yellow]Device is not reporting a setup-mode IP[/bold yellow]\n\n"

        f"[bold]Device IP:[/bold] {host_ip}\n"
        f"[bold]Expected setup IP:[/bold] 10.22.22.x\n\n"

        f"[bold]This can happen for two normal reasons:[/bold]\n\n"

        f"[bold]1) Your PC is on your normal Wi-Fi[/bold]\n"
        f"Your computer may have auto-reconnected to '{target_ssid}'.\n"
        f"In this case, switch to the WeMo setup Wi-Fi and restart this tool.\n\n"

        f"[bold]2) The device already joined your Wi-Fi[/bold]\n"
        f"The device may be partially or fully provisioned and is now responding\n"
        f"from your main network, even if its setup Wi-Fi is still visible.\n\n"

        f"[bold]If the device is already working:[/bold]\n"
        f"You can safely exit - provisioning is not needed.\n\n"

        f"[bold]Recommended next steps:[/bold]\n"
        f"• Power cycle the device\n"
        f"• Factory reset (hold reset button 10–20 seconds)\n",

        title="Device Not in Setup Mode",
        style="yellow"
    ))

    return Confirm.ask("Exit setup without provisioning?", default=True)


# ============================================================
# DEVICE SETUPS
# ============================================================

## -- ## PRE-SETUP ## -- ##
def presetup():
    """
    Simple manual entry for SSID and password. No auto-detection, etc. Win11 location BS needed otherwise.
    Save user network config to config.json to re-use later.
    """
    # Band reminder
    console.print(Panel(
        "[yellow]Reminder:[/yellow] WeMo devices require a [bold]2.4 GHz[/bold] network.\n"
        "Most modern routers have separate SSIDs for 2.4/5 GHz, or a combined one - ensure this SSID is 2.4 GHz capable.\n"
        "Security: WPA2 is ideal; WPA3 may work but is less tested with WeMo.",
        title="Quick Check"
    ))

    while True:
        ssid = Prompt.ask("Enter the SSID (network name)").strip()
        if ssid:
            break
        console.print("[red]SSID cannot be empty. Try again.[/red]")

    while True:
        # 1. Prompt for password
        pw1 = Prompt.ask(f"Enter password for [bold]{ssid}[/bold]", password=False)
        
        # 2. Confirm
        pw2 = Prompt.ask("Confirm password", password=False)

        if pw1 == pw2:
            if not pw1 and not Confirm.ask("You entered an [bold red]EMPTY[/bold red] password. Is the network open/unsecured?"):
                continue
            password = pw1
            break
        else:
            console.print("[bold red]Passwords do not match![/bold red] Please try again.\n")
            log.warning("Password mismatch during entry.")

    # Show final confirmation
    console.print(Panel(
        f"SSID:     [bold]{ssid}[/bold]\n"
        f"Password: [bold yellow]{password}[/bold yellow]\n\n"
        "Double-check spelling and characters above!",
        title="Final Network Verification"
    ))

    if not Confirm.ask("Use these credentials?"):
        return presetup()  # Restart if they change mind

    # Minimal config
    config = {
        "ssid": ssid,
        "password": password,
        "timestamp": time.time()
    }
    
    with open(CONFIG_FILE, "w") as f:
        json.dump(config, f, indent=4)
    
    log.info(f"Network configuration for '{ssid}' saved to config.json")
    return config

# stray imports, put these up top later.
from pywemo.exceptions import APNotFound, SetupException, ActionException

## -- ## MAIN SETUP ## -- ##
def setup_device(device, config, device_info):
# --- Setup Stage 1 --- start actual device setup after info has been gathered.
    ssid = config["ssid"]
    password = config["password"]
    mac = device_info["mac"]
    dev_name = device_info["name"]
    dev_model = device_info["model"]
    
    log.info(f"Provisioning {dev_name} ({dev_model}, MAC: {mac}) with SSID: {ssid}")

    # Initial settle
    log.info(f"Device [green]FOUND[/green]. Waiting initial settle period...")
    time.sleep(8)

    # --- Attempt provisioning
    MAX_ATTEMPTS = 3
    provisioned = False

    for attempt in range(1, MAX_ATTEMPTS + 1):
        log.info(f"Provisioning attempt {attempt}/{MAX_ATTEMPTS}...")

        try:
            if hasattr(device, 'update'):
                try:
                    device.update()
                    time.sleep(1)
                except:
                    pass

            log.info("Sending credentials (timeout=40, attempts=10, status_delay=4.0)")
            device.setup(
                ssid=ssid,
                password=password,
                timeout=40,
                connection_attempts=10,
                status_delay=4.0   # slower = less aggressive retry spam in logs
            )

            log.info("[green]Library reports clean success (rare case)[/green]")
            provisioned = True
            break

        except pywemo.exceptions.APNotFound:
            log.warning(f"[attempt #{attempt}] Device unable to find '{ssid}' (yet) [bold]Retrying...[/bold]")
            time.sleep(8)

        except (pywemo.exceptions.SetupException,
                pywemo.exceptions.ActionException,
                Exception) as e:

            log.info(
                "This is the most common success pattern: the device accepted the credentials, "
                "began connecting to Wi-Fi, and temporarily stopped responding."
            )

            provisioned = True
            break  # stop retrying - treat as sent successfully


    if not provisioned:
        log.error("Provisioning failed after all attempts")
        console.print(
            "[bold red]Credentials could not be sent.[/bold red]\n"
            "Possible causes:\n"
            "• Device is not in setup mode\n"
            "• Network is unreachable\n"
            "• Temporary communication failure\n\n"
            "Resolution:\n"
            "Reset the device and try again."
        )

        return False

# --- Setup Stage 2 --- VERIFICATION (device should be connected/connecting to wifi at this point)
    console.print(Panel(
        "[bold]Credentials sent successfully - the device is now processing.[/bold]\n\n"
        "• [yellow]WAIT[/yellow] for the Wemo's light to change (usually stops blinking).\n"
        "• Your PC might disconnect from WeMo.Setup; this is normal.\n"
        "• This transition typically takes 30-60 seconds.",
        title="Provisioning Started",
        style="yellow"
    ))

    # Monitor reachability
    log.info("Monitoring device status on setup network (Stability Check)...")
    consecutive_failures = 0
    start_time = time.time()

    while time.time() - start_time < 90:
        try:
            # Lightweight property check
            _ = device.friendly_name
            consecutive_failures = 0 
            time.sleep(2)
        except Exception:
            consecutive_failures += 1
            log.debug(f"Device heartbeat failed (count: {consecutive_failures})")
            
            # Attempt to proceed only if wemo actually disconnected
            if consecutive_failures >= 4: 
                log.info("Device confirmed unreachable. It is now joining your main network.")
                break
        time.sleep(1)

    # Forced cooldown, verify the Wemo has finished its DHCP handshake etc things.
    console.print("[cyan] -- Waiting 15 seconds for Wemo stack to reticulate --[/cyan]")
    time.sleep(14) # under promise, over deliver.

    console.print(Panel(
        f"[bold]ACTION REQUIRED:[/bold]\n"
        f"1. Manually connect your PC to the target Wi-Fi: [bold green]{ssid}[/bold green]\n"
        f"2. Ensure your PC has a stable connection (Internet access restored).\n",
        title="Switch to Main Wi-Fi Now",
        style="cyan"
    ))

    #input("Press ENTER once connected to Wi-Fi...")
    Prompt.ask("Press [bold green]ENTER[/bold green] once connected to the target Wi-Fi")
    console.print("")

    # "Network Stack Cooling Period"
    # Often take 5-10 seconds to update the local routing table .
    log.info("PC rejoined main network. Cooling down network stack for 12s...")
    console.print("[bold cyan] -- Reticulating network interface splines...[/bold cyan]")
    time.sleep(11) 

    console.print("[bold cyan] -- Scanning network for WeMo devices...[/bold cyan]")
    
    # Increase retries for the final discovery phase
    #devices_after, _ = discover_devices_with_retry(retries=10, retry_delay=10)
    
#---# Use targeted dicovery function this time. #---#
    
    # Passing mac address to find exact wemo device.
    devices_after, _ = discover_target_device(mac, retries=10, retry_delay=10)
    
    if not devices_after:
        console.print(f"[yellow]No devices were found during the re-scan.\n"
                      f"Please confirm your PC is connected to '{ssid}' and try again.[/yellow]")
        return False

    device_found = False
    matched_device = None
    
    for d in devices_after:
        d_mac = getattr(d, 'mac', None)
        d_name = d.name
        d_model = getattr(d, 'model_name', None) or getattr(d, 'device_type', 'Unknown')

        if d_mac == mac or (d_name == dev_name and d_model == dev_model):
            device_found = True
            matched_device = d
            log.info(f"FOUND match: {d_name} ({d_model}) at {d.host} (MAC: {d_mac})")
            break

    if device_found:
        console.rule(" SETUP FINISHED ")
        console.print(Panel(
            f"[bold green]Device Successfully Provisioned[/bold green]\n\n"
            f"Device '{dev_name}' ({dev_model}, MAC {mac}) found on main network at {matched_device.host}.\n"
            "Setup complete!",
            style="green"
        ))
        return True
    else:
        console.print(Panel(
            "[bold red]Device Not Found on Main Network[/bold red]\n\n"
            f"Expected device:\n"
            f"  Name: {dev_name}\n"
            f"  Model: {dev_model}\n"
            f"  MAC: {mac}\n\n"
            "Recommended next steps:\n"
            "• Wait 1–3 minutes and re-run the script\n"
            f"• Confirm your PC is connected to '{ssid}' (not WeMo.Setup)\n"
            f"• Check your router's client list for MAC address {mac}\n"
            "• Power cycle the WeMo device\n"
            "• Verify the Wi-Fi password and confirm the network supports 2.4 GHz\n",
            style="red"
        ))

        return False

SNAIL = r"""
      .----.   @   @
     / .--. \   \ /
    | |    | |   |
    |  .__.  |  / \
    |        |-'   `
   /          \      [ THE SUCCESS SNAIL HAS ARRIVED ]
  |  .-.  .-.  |     [ SUCCESS! ]
  '--'  '--'  '--'
"""
        
def main():
    # Header and Initialization
    console.rule(f"[bold blue]{PROG_TITLE}[/bold blue] [bold magenta]v{VERSION}[/bold magenta]")
    log.debug(f"Log file created: {logfile}")
    log.info(f"{PROG_TITLE} v{VERSION} starting")
    
    enable_soap_logging()

    # Load or run first-time setup
    config = load_config()
    if not config:
        config = presetup()

    # User Connection Step
    console.print(Panel(f"[bold magenta]Please[/bold magenta] connect your PC to the [bold]WeMo.Setup Wi-Fi network[/bold].", title="Device Discovery"))
    input("Press ENTER when connected...")

    # Discovery with Retries - returns list + pre-selected device info
    devices, device_info = discover_devices_with_retry(retries=6)

    if not devices or device_info is None:
        fatal("No WeMo devices found. Check your Wi-Fi connection to the device.")

    # IP check & optional skip
    if check_device_ip_and_warn(device_info, config):
        console.print("[bold yellow]Setup exited without provisioning.[/bold yellow]")
        return  # exit main early

    # If not skipping, continue
    log.info("Device subnet [green]VERIFIED![/green]")
    #console.print("[cyan]Starting provisioning...[/cyan]")
    console.rule(" Provisioning ")
    time.sleep(0.5)

    # Find the matching device object using the MAC from device_info
    mac = device_info["mac"]
    target_device = next(
        (d for d in devices if getattr(d, 'mac', None) == mac),
        None
    )

    if target_device is None:
        log.warning("MAC match failed - falling back to first device")
        target_device = devices[0]

    # Device Found
    log.info(f"Found Device: {device_info['name']} ({device_info['model']}) | MAC: {device_info['mac']} ({device_info['host']})")
    
    # Pass device information to setup function - proceed with setup.
    success = setup_device(target_device, config, device_info)
  
    # Setup pass or fail.
    if success:
        console.print(f"\n[bold green]{SNAIL}[/bold green]")
        console.print("\n[bold green]Setup complete![/bold green]\n")
    else:
        console.print("[bold red]Setup did not complete successfully. :( [/bold red]")
    
    input("Press buttons to exit.")
    # end.

    
if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        console.print("\n[yellow]Interrupted by user.[/yellow]")
    except Exception:
        log.exception("Unhandled exception in main")