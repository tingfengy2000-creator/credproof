import sys
from PIL import Image
src, y0, y1, out = sys.argv[1], int(sys.argv[2]), int(sys.argv[3]), sys.argv[4]
x0 = int(sys.argv[5]) if len(sys.argv) > 5 else 0
x1 = int(sys.argv[6]) if len(sys.argv) > 6 else None
im = Image.open(src).convert('RGB')
x1 = x1 or im.size[0]
c = im.crop((x0, y0, x1, y1))
c.save(out, quality=88)
print(out, c.size)
