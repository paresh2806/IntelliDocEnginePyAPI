import os
# from Backend.deepdoctection.deepdoctection import analyzer
import cv2
from deepdoctection.analyzer import get_dd_analyzer
# from  deepdoctection.deepdoctection.analyzer import get_dd_analyzer
analyzer=get_dd_analyzer()
# df=analyzer.analyze(path=r'OCR/Image_files/2img')
df=analyzer.analyze(path=r'OCR/Image_files')
df.reset_state()
page=next(iter(df))
print(page.get_text())
