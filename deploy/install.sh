#!/bin/sh
# Install the agent on a vehicle/dock computer (Debian/Ubuntu/Jetson/RPi OS).
set -e
sudo mkdir -p /opt/fleetdebug /etc/fleetdebug /var/lib/fleetdebug
sudo cp -r "$(dirname "$0")/../fleetdebug" /opt/fleetdebug/
[ -f /etc/fleetdebug/agent.json ] || sudo cp "$(dirname "$0")/agent.example.json" /etc/fleetdebug/agent.json
sudo cp "$(dirname "$0")/fleetdebug-agent.service" /etc/systemd/system/
sudo systemctl daemon-reload
sudo systemctl enable --now fleetdebug-agent
echo "Edit /etc/fleetdebug/agent.json, then: sudo systemctl restart fleetdebug-agent"
echo "Optional: pip install pymavlink pyulog  (MAVLink telemetry + .ulg/.bin log parsing)"
