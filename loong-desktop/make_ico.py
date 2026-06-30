from PIL import Image
import os

img = Image.open(r'D:\COGU AGENT\cogu_agent\loong-desktop\assets\logo.jpg')
img_rgba = img.convert('RGBA')
sizes = [(16,16),(32,32),(48,48),(64,64),(128,128),(256,256)]
resized = [img_rgba.resize(s, Image.LANCZOS) for s in sizes]

ico_path = r'D:\COGU AGENT\cogu_agent\loong-desktop\assets\logo.ico'
resized[0].save(ico_path, format='ICO', sizes=sizes, append_images=resized[1:])
print(f'ICO created: {os.path.getsize(ico_path)} bytes')
