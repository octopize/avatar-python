import re
import sys

doc = open(sys.argv[1])
blocks = re.findall(r"\n```python\n(.*?)\n```", doc.read(), re.DOTALL)
print("\n\n\n".join(block for block in blocks))
