#!/usr/bin/env bash
# One-time setup for a fresh cloud session: Python packages, EGL for MediaPipe, ffmpeg, rclone.
set -euo pipefail
cd "$(dirname "$0")"

pip install --quiet --root-user-action=ignore -r requirements.txt
if ! ldconfig -p | grep -q libEGL.so.1; then
  (apt-get install -y -q libegl1 libgles2 >/dev/null 2>&1) || (apt-get update -q >/dev/null && apt-get install -y -q libegl1 libgles2 >/dev/null)
fi
if ! command -v ffmpeg >/dev/null; then
  ln -sf "$(python3 -c 'import imageio_ffmpeg; print(imageio_ffmpeg.get_ffmpeg_exe())')" /usr/local/bin/ffmpeg
fi
if ! command -v rclone >/dev/null; then
  GOPATH=/tmp/gobuild GOFLAGS=-mod=mod go install github.com/rclone/rclone@latest
  ln -sf /tmp/gobuild/bin/rclone /usr/local/bin/rclone
fi
ffmpeg -hide_banner -version | head -1
rclone version | head -1
python3 -c "import cv2, mediapipe, PIL; print('python deps ok')"
