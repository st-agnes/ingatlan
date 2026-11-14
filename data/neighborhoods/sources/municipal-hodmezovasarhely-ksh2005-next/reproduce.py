#!/usr/bin/env python3
from pathlib import Path
import subprocess,sys,os
P=Path(__file__).resolve().parent
for n in ['extract-native.py','prepare-road-inputs.py','verify-road-pbf.py','derive-estimated-world.py','render-review.py','verify-packet.py']:
 subprocess.run([sys.executable,str(P/n)],check=True,env=os.environ.copy())
