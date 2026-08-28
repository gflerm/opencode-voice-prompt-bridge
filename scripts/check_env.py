"""Environment diagnostic: Python, platform, CUDA/GPU, audio devices."""

import platform
import sys


def check_python() -> None:
    print(f"Python      : {sys.version.split()[0]} ({platform.architecture()[0]})")
    print(f"Platform    : {platform.platform()}")


def check_cuda() -> str:
    import ctranslate2

    count = ctranslate2.get_cuda_device_count()
    print(f"CTranslate2 : {ctranslate2.__version__}")
    if count == 0:
        print("CUDA        : not available -> CPU inference will be used")
        return "cpu"
    print(f"CUDA        : {count} device(s) found")
    supported = ctranslate2.get_supported_compute_types("cuda")
    print(f"Compute tbl : {supported}")
    return "cuda"


def check_audio() -> None:
    import sounddevice as sd

    print(f"PortAudio   : default input = {sd.default.device[0]}")
    for idx, dev in enumerate(sd.query_devices()):
        if int(dev["max_input_channels"]) > 0:
            print(f"  [{idx}] {dev['name']}  ({dev['max_input_channels']} ch, {int(dev['default_samplerate'])} Hz)")


def main() -> int:
    check_python()
    try:
        device = check_cuda()
    except Exception as exc:
        print(f"CUDA        : probe failed ({exc}) -> CPU inference will be used")
        device = "cpu"
    try:
        check_audio()
    except Exception as exc:
        print(f"Audio       : probe failed ({exc})")
        return 1
    print(f"\nSuggested config: device = \"{device}\"")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
