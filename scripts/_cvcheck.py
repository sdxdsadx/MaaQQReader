import sys
try:
    import cv2
    import numpy
    print("cv2", cv2.__version__, "| numpy", numpy.__version__)
except Exception as e:
    print("CV2_MISSING:", type(e).__name__, e)
    sys.exit(1)
