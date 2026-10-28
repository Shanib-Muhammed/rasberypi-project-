#!/usr/bin/env python3
"""VARODE local dashboard server.

Runs on the Raspberry Pi and needs NO internet. Open the address it prints
from any phone or laptop connected to the same Wi-Fi / mobile hotspot.
Python standard library only - nothing extra to install.
"""
import hmac
import json
import os
import subprocess
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from urllib.parse import unquote, urlparse

BASE_DIR = os.path.expanduser("~/roadbot")
PHOTO_DIR = os.path.join(BASE_DIR, "photos")
WEB_DIR = os.path.join(BASE_DIR, "web")
KEY_FILE = os.path.expanduser("~/.roadbot.env")
LOCATION_FILE = os.path.join(BASE_DIR, "location.json")
PORT = 8000
MAX_REPORTS = 100

TYPES = {
    ".html": "text/html; charset=utf-8",
    ".js": "text/javascript; charset=utf-8",
    ".css": "text/css; charset=utf-8",
    ".jpg": "image/jpeg",
}

os.makedirs(PHOTO_DIR, exist_ok=True)

DEFAULT_LOCATION = {"latitude": 10.7735, "longitude": 76.3775}


def load_location():
    """Load the operator-selected location used by future camera reports."""
    try:
        with open(LOCATION_FILE, "r", encoding="utf-8") as file:
            saved = json.load(file)
        latitude = float(saved["latitude"])
        longitude = float(saved["longitude"])
        if -90 <= latitude <= 90 and -180 <= longitude <= 180:
            return {"latitude": latitude, "longitude": longitude}
    except (OSError, ValueError, KeyError, TypeError):
        pass
    return DEFAULT_LOCATION.copy()


def save_location(latitude, longitude):
    """Atomically save coordinates so the camera never reads a half-written file."""
    location = {"latitude": latitude, "longitude": longitude}
    temporary = LOCATION_FILE + ".tmp"
    with open(temporary, "w", encoding="utf-8") as file:
        json.dump(location, file, indent=2)
    os.replace(temporary, LOCATION_FILE)
    return location


def read_setting(name):
    """Read NAME=value from ~/.roadbot.env (or the environment)."""
    try:
        with open(KEY_FILE, "r", encoding="utf-8") as file:
            for line in file:
                key, _, value = line.strip().partition("=")
                if key == name:
                    return value.strip().strip("'\"")
    except OSError:
        pass
    return os.environ.get(name, "")


ADMIN_PASSWORD = read_setting("ADMIN_PASSWORD")


def load_reports():
    """Every report = one .jpg photo + one .json file with the same name."""
    reports = []
    for name in os.listdir(PHOTO_DIR):
        stem, ext = os.path.splitext(name)
        if ext != ".json":
            continue
        try:
            with open(os.path.join(PHOTO_DIR, name), "r", encoding="utf-8") as file:
                report = json.load(file)
        except (OSError, ValueError):
            continue
        photo = stem + ".jpg"
        if (
            isinstance(report, dict)
            and "id" in report
            and os.path.isfile(os.path.join(PHOTO_DIR, photo))
        ):
            report["photo"] = photo
            reports.append(report)
    reports.sort(key=lambda r: str(r.get("timestamp", "")), reverse=True)
    return reports


class Handler(BaseHTTPRequestHandler):
    def log_message(self, *args):  # keep the terminal quiet
        pass

    def reply(self, code, body, ctype="application/json", cache="no-store"):
        if not isinstance(body, bytes):
            body = json.dumps(body).encode("utf-8")
        self.send_response(code)
        self.send_header("Content-Type", ctype)
        self.send_header("Content-Length", str(len(body)))
        self.send_header("Cache-Control", cache)
        self.end_headers()
        self.wfile.write(body)

    def send_file(self, folder, name, cache):
        name = os.path.basename(name)  # blocks ../ tricks
        ext = os.path.splitext(name)[1].lower()
        path = os.path.join(folder, name)
        if ext not in TYPES or not os.path.isfile(path):
            return self.reply(404, {"error": "Not found"})
        with open(path, "rb") as file:
            self.reply(200, file.read(), TYPES[ext], cache)

    def do_GET(self):
        path = unquote(urlparse(self.path).path)
        if path == "/api/reports":
            reports = load_reports()
            self.reply(200, {"total": len(reports), "reports": reports[:MAX_REPORTS]})
        elif path == "/api/location":
            self.reply(200, load_location())
        elif path.startswith("/photos/"):
            self.send_file(PHOTO_DIR, path[len("/photos/"):], "public, max-age=86400")
        else:
            self.send_file(WEB_DIR, "index.html" if path == "/" else path, "no-cache")

    def do_POST(self):
        path = urlparse(self.path).path
        try:
            length = min(int(self.headers.get("Content-Length", 0)), 10000)
            data = json.loads(self.rfile.read(length) or b"{}")
        except ValueError:
            return self.reply(400, {"success": False, "error": "Bad request"})
        if not isinstance(data, dict):
            data = {}

        if not ADMIN_PASSWORD:
            return self.reply(403, {
                "success": False,
                "error": "ADMIN_PASSWORD is not set in ~/.roadbot.env on the Raspberry Pi",
            })

        supplied = self.headers.get("X-Admin-Password", "") or str(data.get("password", ""))
        if not hmac.compare_digest(supplied.encode(), ADMIN_PASSWORD.encode()):
            return self.reply(401, {"success": False, "error": "Wrong password"})

        if path == "/api/login":
            return self.reply(200, {"success": True})

        if path == "/api/location":
            try:
                latitude = float(data.get("latitude"))
                longitude = float(data.get("longitude"))
            except (TypeError, ValueError):
                return self.reply(400, {"success": False, "error": "Enter numbers for latitude and longitude"})
            if not -90 <= latitude <= 90:
                return self.reply(400, {"success": False, "error": "Latitude must be between -90 and 90"})
            if not -180 <= longitude <= 180:
                return self.reply(400, {"success": False, "error": "Longitude must be between -180 and 180"})
            try:
                location = save_location(latitude, longitude)
            except OSError as error:
                return self.reply(500, {"success": False, "error": f"Could not save location: {error}"})
            return self.reply(200, {"success": True, **location})

        if path == "/api/delete":
            target = str(data.get("id"))
            for report in load_reports():
                if str(report["id"]) == target:
                    stem = os.path.splitext(report["photo"])[0]
                    for ext in (".jpg", ".json"):  # photo first, then the record
                        try:
                            os.remove(os.path.join(PHOTO_DIR, stem + ext))
                        except OSError:
                            pass
                    return self.reply(200, {"success": True})
            return self.reply(404, {"success": False, "error": "Report not found"})

        self.reply(404, {"success": False, "error": "Not found"})


def lan_addresses():
    try:
        out = subprocess.run(
            ["hostname", "-I"], capture_output=True, text=True, timeout=5
        ).stdout
        return [ip for ip in out.split() if "." in ip]
    except (OSError, subprocess.SubprocessError):
        return []


def main():
    if not os.path.isfile(os.path.join(WEB_DIR, "index.html")):
        print("WARNING: No website files found in", WEB_DIR)
    print("\n==============================================")
    print("  VARODE dashboard is running (works offline)")
    print("==============================================")
    print("Open ONE of these on your phone or laptop")
    print("(it must be on the same Wi-Fi / hotspot as the Pi):\n")
    for ip in lan_addresses() or ["<pi-ip-address>"]:
        print(f"    http://{ip}:{PORT}")
    print(f"    http://localhost:{PORT}   (on the Pi itself)")
    if not ADMIN_PASSWORD:
        print("\nNOTE: ADMIN_PASSWORD is not set, so report deletion is disabled.")
    print("\nStop with Ctrl+C\n")
    try:
        ThreadingHTTPServer(("0.0.0.0", PORT), Handler).serve_forever()
    except KeyboardInterrupt:
        print("\nServer stopped.")


if __name__ == "__main__":
    main()
