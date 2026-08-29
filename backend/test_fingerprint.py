import ctypes
import ctypes.wintypes as wintypes
import hashlib

winbio = ctypes.WinDLL('winbio.dll')

WINBIO_TYPE_FINGERPRINT = 0x00000008
WINBIO_POOL_SYSTEM = 0x00000001
WINBIO_FLAG_DEFAULT = 0x00000000

class WINBIO_IDENTITY(ctypes.Structure):
    class _Value(ctypes.Union):
        class _AccountSid(ctypes.Structure):
            _fields_ = [
                ("Size", ctypes.c_ulong),
                ("Data", ctypes.c_byte * 68)
            ]
        _fields_ = [
            ("Null", ctypes.c_ulong),
            ("Wildcard", ctypes.c_ulong),
            ("TemplateGuid", ctypes.c_byte * 16),
            ("AccountSid", _AccountSid)
        ]
    
    _fields_ = [
        ("Type", ctypes.c_ulong),
        ("Value", _Value)
    ]

def capture_fingerprint_hash():
    session = wintypes.HANDLE()
    
    result = winbio.WinBioOpenSession(
        WINBIO_TYPE_FINGERPRINT,
        WINBIO_POOL_SYSTEM,
        WINBIO_FLAG_DEFAULT,
        None,
        0,
        None,
        ctypes.byref(session)
    )
    
    if result != 0:
        print(f"FAILED to open session: {hex(result)}")
        return None
    
    print("Place your finger on the scanner...")
    
    unit_id = ctypes.c_ulong(0)
    identity = WINBIO_IDENTITY()
    sub_factor = ctypes.c_ubyte(0)
    reject_detail = ctypes.c_ulong(0)
    
    winbio.WinBioIdentify.restype = ctypes.HRESULT
    winbio.WinBioIdentify.argtypes = [
        wintypes.HANDLE,
        ctypes.POINTER(ctypes.c_ulong),
        ctypes.POINTER(WINBIO_IDENTITY),
        ctypes.POINTER(ctypes.c_ubyte),
        ctypes.POINTER(ctypes.c_ulong)
    ]
    
    result = winbio.WinBioIdentify(
        session,
        ctypes.byref(unit_id),
        ctypes.byref(identity),
        ctypes.byref(sub_factor),
        ctypes.byref(reject_detail)
    )
    
    winbio.WinBioCloseSession(session)
    
    if result != 0:
        print(f"FAILED: {hex(result & 0xFFFFFFFF)}")
        return None
    
    # Extract SID bytes
    sid_size = identity.Value.AccountSid.Size
    sid_data = bytes([b % 256 for b in identity.Value.AccountSid.Data[:sid_size]])
    
    # Hash the SID — never store raw biometric data
    fingerprint_hash = hashlib.sha256(sid_data).hexdigest()
    
    print(f"SUCCESS - Fingerprint captured!")
    print(f"Hash: {fingerprint_hash[:20]}...")
    
    return fingerprint_hash

if __name__ == "__main__":
    print("Scan 1:")
    hash1 = capture_fingerprint_hash()
    
    print("\nScan 2 — same finger:")
    hash2 = capture_fingerprint_hash()
    
    print(f"\nHash 1: {hash1[:20]}...")
    print(f"Hash 2: {hash2[:20]}...")
    print(f"Hashes match: {hash1 == hash2}")