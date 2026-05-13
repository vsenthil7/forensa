import base64, pathlib, sys
path, b64 = sys.argv[1], sys.argv[2]
pathlib.Path(path).write_bytes(base64.b64decode(b64))
print(f"wrote {path}: {len(b64)} b64 bytes")
