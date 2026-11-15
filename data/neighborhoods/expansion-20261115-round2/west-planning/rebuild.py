#!/usr/bin/env python3
import subprocess,sys
from pathlib import Path
P=Path(__file__).resolve().parent
for rel in ['tata/extract-native.py','tata/build-estates.py','dombovar/derive-circuits.py','build.py','keszthely/build-inventory-estimates.py','build.py']:
 subprocess.run([sys.executable,str(P/rel)],check=True)
