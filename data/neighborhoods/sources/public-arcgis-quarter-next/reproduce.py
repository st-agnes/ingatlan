#!/usr/bin/env python3
"""Offline reproduction with retained local originals. No network/global writes."""
from pathlib import Path
import subprocess,sys,os
P=Path(__file__).resolve().parent
for script in ['derive-debrecen.py','extract-fvs-name-evidence.py','freeze-debrecen-six.py','render-source-review.py','verify-and-manifest.py']:
 subprocess.run([sys.executable,str(P/script)],check=True,env=os.environ.copy())
print('Reproduced source transformations, selected map/name evidence, six estimated candidates and manifest.')
