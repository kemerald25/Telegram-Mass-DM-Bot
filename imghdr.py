import sys

def what(file, h=None):
    """
    Minimal fallback implementation of standard imghdr module
    which was deprecated and removed in Python 3.13+.
    """
    if h is None:
        if isinstance(file, (str, bytes)):
            try:
                with open(file, 'rb') as f:
                    h = f.read(32)
            except Exception:
                return None
        else:
            try:
                location = file.tell()
                h = file.read(32)
                file.seek(location)
            except Exception:
                return None
                
    if not h:
        return None

    # Common image signatures
    if h.startswith(b'\x89PNG\r\n\x1a\n'):
        return 'png'
    if h.startswith(b'\xff\xd8'):
        return 'jpeg'
    if h.startswith(b'GIF87a') or h.startswith(b'GIF89a'):
        return 'gif'
    if h.startswith(b'RIFF') and len(h) >= 12 and h[8:12] == b'WEBP':
        return 'webp'
    if h.startswith(b'BM'):
        return 'bmp'
    return None
