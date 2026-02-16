# pyWeMo Network Configuration Utility `v4.5.69`

A Python-based CLI utility designed to provision WeMo smart devices. 
- This tool handles the discovery, credential handling, and post-connection verification process, to connect WeMo devices to a wi-fi network without the need for the official WeMo/Belkin app.

---

## Gallery
| Step 1: Network Config | Step 2: Device Discovery | Step 3: Verification |
| :---: | :---: | :---: |
| ![Config](https://raw.githubusercontent.com/honeybugserial/pywemo-netconfigutility/main/screenshots/pywemo-NetConfigUtil-01.png) | ![Discovery](https://raw.githubusercontent.com/honeybugserial/pywemo-netconfigutility/main/screenshots/pywemo-NetConfigUtil-02.png) | ![Verification](https://raw.githubusercontent.com/honeybugserial/pywemo-netconfigutility/main/screenshots/pywemo-NetConfigUtil-03.png) |

---

## Features

* **Guided Provisioning**: Step-by-step terminal interface.
* **Fuzzy MAC Discovery**: Automatically handles cases where the WeMo device's MAC address shifts (e.g., ending in `B8:7C` vs `B8:7D`) during the transition from Setup Mode to Network Mode.
* **Automatic Logging**: Detailed SOAP and HTTP transaction logs saved to the `/logs` directory for debugging.
* **Semi-Smart Network Detection**: Warns you if your PC has accidentally hopped off the setup network or if the device has already successfully joined the target Wi-Fi.
* **Semi-Resilient Retries**: Discovery logic with configurable retries to handle the slow network stack of older WeMo hardware.

---

## Prerequisites

* **Python 3.8+**
* **Wi-Fi Card**: Your computer must be able to connect to the WeMo's broadcasted setup SSID (e.g., `WeMo.Setup.XXX`).
* **Network**: A **2.4 GHz** Wi-Fi network (WeMo devices do not support 5 GHz).

### Dependencies
The tool relies on the following libraries:
* `pywemo`: Handles the UPnP/SOAP communication with the device.
* `rich`: Powers the CLI panels, tables, and prompts.
* `requests`: Used for underlying HTTP communication.

---

## Installation

1. **Clone the repository**:
   ```
   git clone [https://github.com/honeybugserial/pywemo-netconfigutility](https://github.com/honeybugserial/pywemo-netconfigutility)
   cd pyWeMo-NetConfigUtil
   ```

2. **Install dependencies**:
   ```
   pip install pywemo rich requests
   ```
   or
   ```
   pip install -r requirements.txt
   ```

3. **Required Files**:
   Verify `logConsole_base.py` is present in the same directory, as it handles the core logging initialization.

---

## Usage

### 1. Preparation
* **Factory Reset** your WeMo device (usually by holding the reset button for 10-15 seconds) until the light blinks orange/white.

### 2. Execution
Run the script:
```
python pyWeMo-NetConfigUtil.py
```

### 3. Workflow
1.  **Network Config**: Enter your target 2.4 GHz SSID and Password. These are saved to `config.json` for future use.
2.  **Discovery**: The tool scans for a device on the `10.22.22.x` subnet.
3.  **Provisioning**: Credentials are sent to the device.
4.  **The Switch**: Once the device starts connecting, you will be prompted to switch your PC back to your **main Wi-Fi**.
5.  **Verification**: The tool will perform a final network scan on your main Wi-Fi to confirm the device arrived safely and report its new IP address.

---

## Configuration
On the first run, the tool creates a `config.json` file:
```json
{
    "ssid": "Your_Network_Name",
    "password": "Your_Password",
    "timestamp": 1700000000.0
}
```
*Note: Delete this file if you need to change the target network for future devices.*

---

## Compiling
Clone Repo:
   ```
   git clone git clone [https://github.com/honeybugserial/pywemo-netconfigutility](https://github.com/honeybugserial/pywemo-netconfigutility)
   cd pyWeMo-NetConfigUtil
   ```

Install pywemo:
	```
	pip install pywemo
	```

Compile:
	```
	python -m PyInstaller --onefile --console --icon icon.ico --collect-all rich --hidden-import pywemo --hidden-import logConsole_base --hidden-import requests.adapters pywemo-NetConfigUtil.py
	```

## Troubleshooting

- The setup process is inherently fragile-sh since it requires switching Wi-Fi networks. If the script fails its probably due to signal drops or latency, move closer to the WeMo device and try again.
- Some verification steps are intentionally sloppy to avoid any involvement with Windows location services. Using more "precise" methods require location permissions that you likely have disabled anyway.
- This is why the script uses a more "blind wait" approach rather than active network monitoring; implementing tighter control over Wi-Fi states would force the script to ask for those OS-level permissions.

| Issue | Likely Cause | Solution |
| :--- | :--- | :--- |
| **"No devices found"** | PC not on WeMo.Setup Wi-Fi. | Reconnect to the WeMo's AP and try again. |
| **"APNotFound"** | Device can't see your router. | Ensure your 2.4 GHz signal is strong and the SSID is correct. |
| **"MAC Shift"** | Standard WeMo behavior. | This tool's fuzzy logic accounts for MACs ending in different characters. |
| **Script hangs at "Scanning"** | Network Stack latency. | Wait for the "Reticulating splines" cooldown to finish; discovery can take up to 60s. |

---

## License
This project is provided "as-is" for personal use. WeMo and Belkin are trademarks of assholes.
