import sys

if sys.version_info < (3, 10):
    raise SystemExit('Python 3.10+ is required.')
try:
    import PIL
except ImportError:
    raise SystemExit('Pillow is missing. Run setup.ps1.')
