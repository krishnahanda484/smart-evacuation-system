import re
import os

paths = ['artifacts/evacuation-dashboard/package.json', 'scripts/package.json']
for p in paths:
    if os.path.exists(p):
        with open(p, 'r') as f:
            content = f.read()
        content = re.sub(r'"catalog:"', '"latest"', content)
        with open(p, 'w') as f:
            f.write(content)
        print(f"Fixed {p}")
