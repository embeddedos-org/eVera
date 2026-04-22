#!/usr/bin/env python3
"""Generate placeholder icons for Vera PWA and Electron."""

import struct
import zlib
from pathlib import Path


def create_png(width: int, height: int, bg_r: int, bg_g: int, bg_b: int) -> bytes:
    """Create a simple solid-color PNG with a 'V' letter."""

    def make_pixel_rows():
        rows = []
        cx, cy = width // 2, height // 2
        for y in range(height):
            row = bytearray()
            for x in range(width):
                # Circle background
                dx, dy = x - cx, y - cy
                radius = min(width, height) // 2 - 2
                if dx * dx + dy * dy <= radius * radius:
                    # Draw a simple "V" shape
                    rel_x = (x - (cx - radius * 0.4)) / (radius * 0.8)
                    rel_y = (y - (cy - radius * 0.3)) / (radius * 0.6)
                    if 0 <= rel_x <= 1 and 0 <= rel_y <= 1:
                        # V shape: two diagonal lines meeting at bottom center
                        left_line = abs(rel_x - rel_y * 0.5) < 0.12
                        right_line = abs(rel_x - (1.0 - rel_y * 0.5)) < 0.12
                        if left_line or right_line:
                            row.extend([255, 255, 255, 255])  # White V
                            continue
                    row.extend([bg_r, bg_g, bg_b, 255])  # Circle fill
                else:
                    row.extend([0, 0, 0, 0])  # Transparent
            rows.append(bytes([0]) + bytes(row))  # Filter byte + row
        return b''.join(rows)

    raw = make_pixel_rows()
    compressed = zlib.compress(raw)

    def chunk(chunk_type: bytes, data: bytes) -> bytes:
        c = chunk_type + data
        crc = zlib.crc32(c) & 0xFFFFFFFF
        return struct.pack('>I', len(data)) + c + struct.pack('>I', crc)

    sig = b'\x89PNG\r\n\x1a\n'
    ihdr = struct.pack('>IIBBBBB', width, height, 8, 6, 0, 0, 0)  # 8-bit RGBA
    return sig + chunk(b'IHDR', ihdr) + chunk(b'IDAT', compressed) + chunk(b'IEND', b'')


def main():
    root = Path(__file__).parent

    sizes = {
        root / "vera" / "static" / "icon-192.png": 192,
        root / "vera" / "static" / "icon-512.png": 512,
        root / "electron" / "icon.png": 256,
        root / "electron" / "tray-icon.png": 32,
    }

    # Vera brand color: blue (#3b82f6)
    for path, size in sizes.items():
        path.parent.mkdir(parents=True, exist_ok=True)
        data = create_png(size, size, 59, 130, 246)
        path.write_bytes(data)
        print(f"Generated {path} ({size}x{size}, {len(data)} bytes)")


if __name__ == "__main__":
    main()
