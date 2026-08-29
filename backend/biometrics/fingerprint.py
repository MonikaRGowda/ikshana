import os
from typing import Any, Optional

DLL_PATH = r"C:\Program Files\Mantra\MFS100\Driver\MFS100Test\MANTRA.MFS100.dll"
MATCH_THRESHOLD = 140

_sdk_loaded = False
_MFS100 = None
_FingerData = None


def _load_sdk() -> None:
    global _sdk_loaded, _MFS100, _FingerData

    if _sdk_loaded:
        return

    if not os.path.exists(DLL_PATH):
        raise RuntimeError(f"Mantra SDK DLL not found: {DLL_PATH}")

    import clr

    clr.AddReference(DLL_PATH)
    from MANTRA import FingerData, MFS100

    _MFS100 = MFS100
    _FingerData = FingerData
    _sdk_loaded = True


def _new_scanner():
    _load_sdk()
    return _MFS100()


def _new_finger_data():
    _load_sdk()
    return _FingerData()


def _template_to_bytes(template: Any) -> bytes:
    if template is None:
        return b""

    if isinstance(template, bytes):
        return template

    if isinstance(template, bytearray):
        return bytes(template)

    if isinstance(template, memoryview):
        return template.tobytes()

    return bytes(bytearray(template))


def _bytes_to_dotnet_template(template: Any):
    _load_sdk()
    from System import Array, Byte

    return Array[Byte](_template_to_bytes(template))


def capture_iso() -> Optional[bytes]:
    """Capture a fingerprint using the MFS100 scanner and return its ISO template."""
    scanner = _new_scanner()

    try:
        print("SDK Version:", scanner.GetSDKVersion())

        ret = scanner.Init()
        if ret != 0:
            print("Scanner init failed:", scanner.GetErrorMsg(ret))
            return None

        try:
            info = scanner.GetDeviceInfo()
            print("Scanner initialized")
            print("Model:", info.Model)
            print("Serial:", info.SerialNo)
        except Exception as e:
            print(f"Scanner initialized, but device info was unavailable: {e}")

        print("Place your finger on the scanner...")
        finger = _new_finger_data()
        result = scanner.AutoCapture(
            finger,
            30000,
            True,
            False,
        )

        ret = int(result[0])
        if ret != 0:
            print("Capture failed:", scanner.GetErrorMsg(ret))
            return None

        if len(result) > 1 and result[1] is not None:
            finger = result[1]

        print("Capture successful")
        print("Quality:", finger.Quality)
        print("NFIQ:", finger.Nfiq)

        return _template_to_bytes(finger.ISOTemplate)

    except Exception as e:
        print(f"Fingerprint capture error: {e}")
        return None

    finally:
        try:
            scanner.Uninit()
        except Exception:
            pass


def match_iso(iso1_bytes: Any, iso2_bytes: Any) -> tuple[bool, int]:
    """Compare two ISO templates using the Mantra MatchISO call."""
    if not iso1_bytes or not iso2_bytes:
        return False, 0

    scanner = _new_scanner()

    try:
        ret = scanner.Init()
        if ret != 0:
            print("Scanner init failed:", scanner.GetErrorMsg(ret))
            return False, 0

        iso1 = _bytes_to_dotnet_template(iso1_bytes)
        iso2 = _bytes_to_dotnet_template(iso2_bytes)

        result = scanner.MatchISO(iso1, iso2, 0)
        print("Raw MatchISO Result:", result)

        ret = int(result[0])
        if ret != 0:
            print("Match failed:", scanner.GetErrorMsg(ret))
            return False, 0

        score = int(result[1])
        return score >= MATCH_THRESHOLD, score

    except Exception as e:
        print(f"Fingerprint match error: {e}")
        return False, 0

    finally:
        try:
            scanner.Uninit()
        except Exception:
            pass


def find_matching_voter(new_iso_bytes: Any, stored_templates: list[dict]) -> Optional[dict]:
    """
    Compare a captured ISO template against stored templates.

    stored_templates must contain records shaped like:
    {"voter_id": "...", "iso_template": <bytes or memoryview>}
    """
    for record in stored_templates:
        is_match, score = match_iso(new_iso_bytes, record.get("iso_template"))
        if is_match:
            print(f"Match found! voter_id: {record.get('voter_id')}, score: {score}")
            return record

    return None
