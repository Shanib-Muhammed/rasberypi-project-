#!/usr/bin/env bash
# VARODE RoadBot installer for Raspberry Pi OS.
#
#   bash install.sh               install only
#   bash install.sh --autostart   install AND start automatically on every boot
#
# Run it as your normal user (NOT with sudo). It asks for sudo when needed.
set -e
cd "$(dirname "$0")"

TARGET="$HOME/roadbot"
ENV_FILE="$HOME/.roadbot.env"

echo
echo "== 1/4  Installing packages (needs internet, one time only) =="
sudo apt update
sudo apt install -y python3 python3-opencv python3-numpy v4l-utils
sudo usermod -aG video "$(id -un)" || true

echo
echo "== 2/4  Copying files to $TARGET =="
mkdir -p "$TARGET/photos" "$TARGET/web"
cp red_detect.py server.py "$TARGET/"
cp web/index.html web/app.js web/style.css "$TARGET/web/"

echo
echo "== 3/4  Admin password (used only to delete reports) =="
if grep -q '^ADMIN_PASSWORD=' "$ENV_FILE" 2>/dev/null; then
  echo "Already set in $ENV_FILE - keeping it."
else
  read -r -s -p "Choose an admin password: " PW
  echo
  if [ -n "$PW" ]; then
    echo "ADMIN_PASSWORD=$PW" >> "$ENV_FILE"
  else
    echo "No password entered - report deletion will stay disabled."
  fi
fi
chmod 600 "$ENV_FILE" 2>/dev/null || true

make_service() {  # $1 = service name, $2 = python file
  sudo tee "/etc/systemd/system/$1.service" > /dev/null <<EOF
[Unit]
Description=VARODE RoadBot ($2)
After=network.target

[Service]
User=$(id -un)
ExecStart=/usr/bin/python3 $TARGET/$2
Restart=always
RestartSec=5

[Install]
WantedBy=multi-user.target
EOF
}

echo
if [ "$1" = "--autostart" ]; then
  echo "== 4/4  Setting up start-on-boot =="
  make_service roadbot-web server.py
  make_service roadbot-camera red_detect.py
  sudo systemctl daemon-reload
  sudo systemctl enable --now roadbot-web roadbot-camera
  echo "Both programs are running and will start on every boot."
else
  echo "== 4/4  Start-on-boot skipped (add it later with: bash install.sh --autostart) =="
fi

echo
echo "=============================================="
echo " Install finished."
if [ "$1" != "--autostart" ]; then
  echo " Start it by hand in two terminals:"
  echo "   python3 ~/roadbot/server.py"
  echo "   python3 ~/roadbot/red_detect.py"
fi
echo " Open the dashboard from a phone/laptop on the same Wi-Fi:"
for ip in $(hostname -I 2>/dev/null); do
  case "$ip" in *.*) echo "   http://$ip:8000" ;; esac
done
echo "=============================================="
