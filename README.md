# VARODE – Raspberry Pi Road Damage Detection (Local Network Version)

A school working model that shows how road damage can be found and reported automatically.
A Raspberry Pi with a USB webcam watches a miniature road, takes a photo when it sees a **red marking**
(the stand-in for a crack), and shows every report on a **website that runs on the Pi itself**.

**It works without internet.** Connect the Pi, a laptop and a phone to the same Wi-Fi or mobile hotspot,
and open the dashboard in any browser. Weak or missing internet can no longer stop photos from appearing.

> **Honest status:** this is a school prototype. It detects the *colour red*, not real cracks, and it uses
> manually set coordinates, not a live GPS module. Change them in **Dashboard administrator → Location settings**. See [Limitations](#limitations).

---

## How it works

```
  USB webcam
      |
      v
  red_detect.py   (Raspberry Pi)
   - finds red regions in each camera frame
   - tracks them so one mark does not make endless photos
   - saves  photo (.jpg) + report (.json)  ->  ~/roadbot/photos/
      |
      v
  server.py       (Raspberry Pi, port 8000)
   - serves the website in  ~/roadbot/web/
   - lists the saved reports and photos
      |
      |  same Wi-Fi / mobile hotspot
      v
  Phone or laptop browser  ->  http://<pi-ip-address>:8000
```

1. **Camera:** the webcam sends frames to `red_detect.py`.
2. **Detection:** each frame is converted to HSV colour space. Pixels that are red (hue 0–8 and 172–179, strong colour,
   not too dark) are kept. Orange, amber and yellow are ignored. Regions bigger than a minimum area count as a detection.
3. **Tracking:** a detection must appear in 3 frames before a photo is taken. Each red mark gets at most
   2 photos. A mark that leaves the camera view is forgotten after 1.5 seconds, so the *next* red mark is always treated as new.
4. **Saving:** the photo (with a green box and the label `CRACK DETECTED`) and a small report file
   (id, time, latitude, longitude) are saved on the Pi. Each new report uses the location selected in dashboard settings.
5. **Dashboard:** `server.py` serves the website. The page asks the server for reports every 5 seconds and shows
   the photo, time and coordinates. Click a photo to enlarge it.
6. **Admin:** reports are public to view. An administrator password is needed to delete reports or change the location for future reports.

---

## What you need

**Hardware**

- Raspberry Pi 3 Model B v1.2 (other Pi models also work)
- USB webcam
- microSD card with Raspberry Pi OS, and a power supply
- A Wi-Fi network or phone hotspot (**2.4 GHz** – the Pi 3 B does not support 5 GHz)
- A miniature road with **red** markings
- A laptop and/or phone to view the dashboard

**Software** (installed for you by `install.sh`): Python 3, OpenCV, NumPy, v4l-utils.
The server uses only the Python standard library.

---

## Project files

| File | What it does |
|------|--------------|
| `red_detect.py` | Camera program: detects red, takes photos, saves reports. `--calibrate` helps tune the colour. |
| `server.py` | Web server: shows the dashboard and the saved reports (port 8000). |
| `web/index.html`, `web/style.css`, `web/app.js` | The dashboard website. |
| `install.sh` | One-command installer (packages, folders, admin password, automatic start-on-boot). |
| `.gitignore` | Keeps photos and passwords out of GitHub. |

After installing, everything lives in `~/roadbot/` on the Pi (photos are in `~/roadbot/photos/`).

---

## Install on the Raspberry Pi

### Step 1 – Put the Pi on your hotspot

1. Turn on your phone's **mobile hotspot** (set it to **2.4 GHz**; on iPhone turn on *Maximize Compatibility*).
2. Connect the Pi to it. With a screen, use the Wi-Fi icon. Without a screen, edit the SD card setup
   in Raspberry Pi Imager, or run `sudo raspi-config` → *System Options* → *Wireless LAN*.
3. Connect your **laptop** to the same hotspot. To control the Pi from the laptop, use SSH:
   `ssh <username>@<pi-ip-address>` (find the Pi's IP in the hotspot's list of connected devices).

> The Pi needs internet **once**, for the install in Step 2. After that the system works offline.

### Step 2 – Download and install

On the Pi (terminal or SSH):

```bash
sudo apt install -y git
git clone https://github.com/Shanib-Muhammed/rasberypi-project-.git
cd rasberypi-project-
bash install.sh
```

The installer asks you to choose an **admin password**, starts the camera and dashboard immediately, and makes both start automatically every time the Pi turns on. At the end it prints the local dashboard URL, for example `http://192.168.43.25:8000`.

### Step 3 – Check the webcam

```bash
ls -l /dev/video*
v4l2-ctl --list-devices
```

You should see `/dev/video0`. If not, check the USB cable and try another USB port.

---

## Run it

After installation, nothing else is needed – power on the Pi and wait about a minute. The dashboard and camera services start automatically.

Window 1 prints the address, for example:

```
    http://192.168.43.25:8000
```

Open that address in the browser of your phone or laptop (it must be on the **same hotspot**).
Hold a red marking in front of the camera – a report with a photo appears on the dashboard within a few seconds.

Press **Ctrl+C** in each window to stop.

> **Tip:** use the IP address, not `raspberrypi.local` – many Android phones cannot open `.local` names.
> If the hotspot gives the Pi a new IP later, run `hostname -I` on the Pi to see it again.

---

## Using the dashboard

- **Reports** appear automatically, newest first. The top cards show the total number and the latest report time.
- **Click a photo** to open it full size. Press `Esc` or click outside to close.
- **Delete a report:** enter the admin password in *Dashboard administrator*, then press **Delete report** on a card. This removes the photo and its record from the Pi.
- **Change future report coordinates:** after signing in, open **Location settings**, enter the latitude and longitude, then select **Save location**. The camera reads the new location automatically for every next report; no code change or restart is needed.
- The **Google Maps link** needs internet. The coordinates are always shown.

---

## Make it detect only red (calibration)

Lighting and webcams change colours. If red is missed, or orange is picked up, calibrate:

```bash
python3 ~/roadbot/red_detect.py --calibrate
```

Put the object in the **centre** of the camera view. It prints values like:

```
H=  4  S=210  V=180  ->  RED
```

| What you see | What to do |
|--------------|-----------|
| Your **red** shows `H` of 9–12 and says `not red` | The camera makes red look orange. Raise `RED_HUE_LOW_MAX` a little (keep it below your orange's `H`), or set `LOCK_WHITE_BALANCE = True`. |
| Your **orange** shows `-> RED` | Lower `RED_HUE_LOW_MAX`. |
| Red in shadow or bright light is `not red` | Lower `MIN_SATURATION` or `MIN_VALUE` slightly. |

Settings are at the top of `red_detect.py` (edit `~/roadbot/red_detect.py` on the Pi, then restart it):

| Setting | Meaning | Default |
|---------|---------|---------|
| `RED_HUE_LOW_MAX` / `RED_HUE_HIGH_MIN` | Red hue range (0–8 and 172–179). Orange is about 10–25. | 8 / 172 |
| `MIN_SATURATION`, `MIN_VALUE` | How strong and bright a colour must be | 90, 50 |
| `MIN_RED_AREA` | Smallest red region (pixels) that counts | 500 |
| `STABLE_FRAMES` | Frames a mark must be seen before a photo | 3 |
| `MAX_PHOTOS_PER_OBJECT` | Photos per red mark | 2 |
| `TRACK_FORGET_SECONDS` | Forget a mark after it leaves view | 1.5 |
| Dashboard Location settings | Manual location written in each new report | 10.7735, 76.3775 |
| `LOCK_WHITE_BALANCE` | Stop the camera shifting colours (not every webcam supports it) | False |

The dashboard port (`PORT = 8000`) is at the top of `server.py`.

---

## Managing the auto-start services

The installer enables these services automatically:

```bash
sudo systemctl status roadbot-web roadbot-camera     # are they running?
sudo systemctl restart roadbot-camera                # restart after editing settings
sudo systemctl stop roadbot-web roadbot-camera       # stop (e.g. to run by hand)
sudo systemctl disable roadbot-web roadbot-camera    # do not start on boot any more
journalctl -u roadbot-camera -f                      # live messages from the camera program
```

## Update to a newer version

```bash
cd ~/rasberypi-project-
git pull
bash install.sh
```

---

## Troubleshooting

| Problem | What to check |
|---------|---------------|
| Page will not open on the phone/laptop | Same hotspot for both? Use `http://<pi-ip>:8000` (not `.local`). Is `server.py` running? Try `http://<pi-ip>:8000/api/reports` – it should show text. |
| Page says *Cannot reach the Raspberry Pi* | The Pi lost the hotspot or `server.py` stopped. Reconnect, then reload. |
| `Cannot open camera` | Run `ls /dev/video*`. Try another USB port. Close other programs using the camera. |
| No photos taken | Run `--calibrate`. Is the red big enough (`MIN_RED_AREA`) and bright enough? |
| Orange is photographed | Lower `RED_HUE_LOW_MAX`; use `--calibrate` on the orange object. |
| Red is not photographed | Use `--calibrate`; see the table above. Make sure the lighting is steady. |
| Delete button does nothing / login fails | Check `ADMIN_PASSWORD=` exists in `~/.roadbot.env`, then use the same password on the page. |
| Report times are wrong | The Pi has no clock battery. Without internet its clock can be wrong. Check with `date`; connect to internet once to fix it. |
| `Address already in use` | Another copy of `server.py` is running. Stop it (`Ctrl+C`, or `sudo systemctl stop roadbot-web`). |
| Old photos do not show | Only reports made by this version are shown. |

---

## Security notes

- The dashboard runs over plain HTTP on your local network. Anyone on the same hotspot can **view** reports.
  Do not reuse a real password as the admin password.
- `~/.roadbot.env` holds the admin password. It is excluded from GitHub by `.gitignore`. Never upload it.
- Photos are excluded from GitHub (`photos/` in `.gitignore`).

## Limitations

- **Colour detection only.** The robot looks for red paint/tape, not real cracks. Real roads would need a trained model
  (for example a neural network trained on crack photos).
- **Manual location, not live GPS.** Latitude/longitude are chosen in dashboard settings. Live GPS (for example a NEO-6M module) needs serial reading and parsing code that is not written yet.
- **Local only.** Reports stay on the Pi's SD card. There is no cloud copy.

## Ideas for the future

- Add a real GPS module and write its coordinates into each report
- Train a crack-detection model to replace the red-colour step
- Add an optional cloud upload that retries when internet returns
- Export reports to a spreadsheet or PDF

---

## Related project

The ESP8266 car-control code, wiring notes and hardware documentation are in the main repository:
[varoode-school-working-model](https://github.com/Shanib-Muhammed/varoode-school-working-model).

*VARODE school project – road monitoring prototype.*
