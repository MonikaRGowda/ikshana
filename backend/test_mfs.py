import clr
import sys

# Load Mantra SDK
dll_path = r"C:\Program Files\Mantra\MFS100\Driver\MFS100Test\MANTRA.MFS100.dll"
clr.AddReference(dll_path)

from MANTRA import MFS100, FingerData
from System import Int32

scanner = MFS100()


def capture_fingerprint(title):
    print(f"\n{title}")
    print("Place your finger on the scanner...")

    finger = FingerData()

    result = scanner.AutoCapture(
        finger,
        30000,      # 30 second timeout
        True,       # Show Preview
        False       # Disable finger detection
    )

    ret = int(result[0])

    if ret != 0:
        print("Capture Failed!")
        print("Error:", scanner.GetErrorMsg(ret))
        return None

    # pythonnet may return FingerData in tuple
    if len(result) > 1 and result[1] is not None:
        finger = result[1]

    print("Capture Successful!")
    print("Quality :", finger.Quality)
    print("NFIQ    :", finger.Nfiq)

    return finger.ISOTemplate


try:

    print("=" * 45)
    print("      MANTRA Fingerprint Matcher")
    print("=" * 45)

    print("SDK Version :", scanner.GetSDKVersion())

    ret = scanner.Init()

    if ret != 0:
        print(scanner.GetErrorMsg(ret))
        sys.exit()

    print("Scanner Initialized")

    info = scanner.GetDeviceInfo()

    print("\nDevice")
    print("---------------------")
    print("Model :", info.Model)
    print("Serial:", info.SerialNo)
    print("---------------------")

    # --------------------------
    # First Scan
    # --------------------------

    iso1 = capture_fingerprint("SCAN 1")

    if iso1 is None:
        sys.exit()

    input("\nLift finger.\nPress ENTER and place the SAME finger again...")

    # --------------------------
    # Second Scan
    # --------------------------

    iso2 = capture_fingerprint("SCAN 2")

    if iso2 is None:
        sys.exit()

    # --------------------------
    # Match
    # --------------------------

    print("\nMatching fingerprints...")

    # pythonnet returns a tuple because score is an out parameter
    result = scanner.MatchISO(
        iso1,
        iso2,
        0
    )

    print("Raw MatchISO Result:", result)

    ret = int(result[0])

    if ret != 0:
        print("Match failed!")
        print(scanner.GetErrorMsg(ret))
        sys.exit()

    score = int(result[1])

    print("\n==========================")
    print("MATCH SCORE :", score)
    print("==========================")

    if score >= 140:
        print("✅ SAME FINGER")
    else:
        print("❌ DIFFERENT FINGER")

except Exception as e:
    print(f"Error: {e}")
    sys.exit()