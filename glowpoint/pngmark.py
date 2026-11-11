"""Mark the PNG files that glowpoint writes, so they are not used as a drawing by mistake.

The mark is a standard PNG text chunk (Software: glowpoint ...). It does not change the pixels.
"""
import struct, zlib

KEY = b"Software"
VALUE = b"glowpoint output - not an original drawing"


def _chunks(data):
    pos = 8
    while pos < len(data):
        n = struct.unpack(">I", data[pos:pos+4])[0]; typ = data[pos+4:pos+8]
        yield pos, typ, data[pos+8:pos+8+n]
        pos += 12 + n


def mark(path):
    """Add the mark to a PNG file (no change for other formats)."""
    if not path.lower().endswith(".png"): return
    data = open(path, "rb").read()
    if data[:8] != b"\x89PNG\r\n\x1a\n" or is_marked(path): return
    body = KEY + b"\x00" + VALUE
    chunk = struct.pack(">I", len(body)) + b"tEXt" + body + struct.pack(">I", zlib.crc32(b"tEXt" + body) & 0xffffffff)
    end = data[8:8+4+4+13+4]                                   # IHDR is always first: insert after it
    open(path, "wb").write(data[:8] + end + chunk + data[8+len(end):])


def is_marked(path):
    try:
        data = open(path, "rb").read()
    except OSError:
        return False
    if data[:8] != b"\x89PNG\r\n\x1a\n": return False
    for _, typ, body in _chunks(data):
        if typ == b"tEXt" and body.startswith(KEY + b"\x00") and b"glowpoint" in body: return True
        if typ == b"IDAT": return False
    return False


def write(path, img):
    """cv2.imwrite and mark."""
    import cv2
    ok = cv2.imwrite(path, img)
    mark(path)
    return ok
