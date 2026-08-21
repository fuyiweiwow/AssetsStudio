from __future__ import annotations

import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parent
STAGE9 = ROOT.parent / "stage9_hunyuan_adapter_transfer_v1"
if str(STAGE9) not in sys.path:
    sys.path.insert(0, str(STAGE9))

import audit_hunyuan_jacket_adapter_v1 as audit  # noqa: E402


audit.GARMENT_NAME = "Wearable_Adventurer_TorsoOuterV1"
audit.MASK_NAME = "WearableMask_AdventurerTorsoOuterV1"
audit.SHOULDER_BRIDGE_LIMITS = {
    "front": {"inner": 1.43, "middle": 1.42, "outer": 1.40},
    "back": {"inner": 1.47, "middle": 1.42, "outer": 1.42},
}


if __name__ == "__main__":
    raise SystemExit(audit.main())
