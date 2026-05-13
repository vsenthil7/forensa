import base64
import pathlib
import sys

target, b64_path = sys.argv[1], sys.argv[2]
b64 = pathlib.Path(b64_path).read_text(encoding="utf-8").strip()
pathlib.Path(target).write_bytes(base64.b64decode(b64))
print(f"wrote {target}: {len(b64)} b64 bytes")
