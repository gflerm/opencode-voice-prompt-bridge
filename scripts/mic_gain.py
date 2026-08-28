"""Read/adjust Windows capture (microphone) endpoint levels.

Usage:
  .venv\\Scripts\\python.exe scripts\\mic_gain.py            # list capture devices + levels
  .venv\\Scripts\\python.exe scripts\\mic_gain.py set <index> <0-100>
"""

from __future__ import annotations

import sys
from typing import Any

from comtypes import CLSCTX_ALL, POINTER, cast
from pycaw.constants import CLSID_MMDeviceEnumerator, DEVICE_STATE, EDataFlow
from pycaw.pycaw import AudioUtilities, IAudioEndpointVolume, IMMDeviceEnumerator


def capture_endpoints() -> list[tuple[int, str, float, Any]]:
    enumerator = AudioUtilities.GetDeviceEnumerator()
    collection = enumerator.EnumAudioEndpoints(EDataFlow.eCapture.value, DEVICE_STATE.ACTIVE.value)
    endpoints = []
    for i in range(collection.GetCount()):
        dev = collection.Item(i)
        friendly = AudioUtilities.CreateDevice(dev).FriendlyName
        interface = dev.Activate(IAudioEndpointVolume._iid_, CLSCTX_ALL, None)
        volume = cast(interface, POINTER(IAudioEndpointVolume))
        level = volume.GetMasterVolumeLevelScalar()
        endpoints.append((i, friendly, level, volume))
    return endpoints


def main() -> int:
    args = sys.argv[1:]
    endpoints = capture_endpoints()

    if not args:
        print("Active capture endpoints:")
        for i, name, level, _volume in endpoints:
            print(f"  [{i}] {name:60s} level={level * 100:5.1f}%")
        return 0

    if len(args) != 3 or args[0] != "set":
        print(__doc__)
        return 2
    index, percent = int(args[1]), float(args[2])
    if not (0 <= percent <= 100):
        print("volume must be 0-100")
        return 2
    for i, name, _level, volume in endpoints:
        if i == index:
            volume.SetMasterVolumeLevelScalar(percent / 100.0, None)
            new_level = volume.GetMasterVolumeLevelScalar()
            print(f"[{i}] {name}: level={new_level * 100:.1f}%")
            return 0
    print(f"no capture endpoint with index {index}")
    return 1


if __name__ == "__main__":
    raise SystemExit(main())
