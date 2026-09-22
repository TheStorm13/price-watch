#!/usr/bin/env sh
set -eu

Xvfb :99 -screen 0 1440x900x24 -ac -nolisten tcp >/tmp/xvfb.log 2>&1 &
xvfb_pid=$!

i=0
while [ ! -S /tmp/.X11-unix/X99 ]; do
    i=$((i + 1))
    if [ "$i" -ge 50 ]; then
        echo "Xvfb не запустился" >&2
        exit 1
    fi
    sleep 0.1
done

x11vnc -display :99 -forever -shared -nopw -rfbport 5900 >/tmp/x11vnc.log 2>&1 &
x11vnc_pid=$!
websockify --web=/usr/share/novnc 6080 localhost:5900 >/tmp/novnc.log 2>&1 &
novnc_pid=$!

cleanup() {
    kill "$novnc_pid" "$x11vnc_pid" "$xvfb_pid" 2>/dev/null || true
}
trap cleanup EXIT INT TERM

exec "$@"
