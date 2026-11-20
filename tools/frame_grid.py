"""Render a frame crop with a labelled pixel grid, to mark landmarks precisely by eye."""
import sys, cv2
def main(src, dst, x0=0, y0=0, x1=None, y1=None, step=50, scale=1.0):
    im = cv2.imread(src); H, W = im.shape[:2]
    x1 = x1 or W; y1 = y1 or H
    c = im[y0:y1, x0:x1].copy()
    for x in range((x0 // step + 1) * step, x1, step):
        cv2.line(c, (x - x0, 0), (x - x0, y1 - y0), (0, 255, 0) if x % 100 == 0 else (0, 120, 0), 1)
        if x % 100 == 0:
            cv2.putText(c, str(x), (x - x0 + 2, 12), 0, 0.4, (0, 255, 0), 1)
    for y in range((y0 // step + 1) * step, y1, step):
        cv2.line(c, (0, y - y0), (x1 - x0, y - y0), (0, 255, 0) if y % 100 == 0 else (0, 120, 0), 1)
        if y % 100 == 0:
            cv2.putText(c, str(y), (2, y - y0 - 2), 0, 0.4, (0, 255, 0), 1)
    if scale != 1:
        c = cv2.resize(c, None, fx=scale, fy=scale)
    cv2.imwrite(dst, c)
if __name__ == "__main__":
    a = sys.argv
    main(a[1], a[2], *[int(v) for v in a[3:7]], step=int(a[7]) if len(a) > 7 else 50,
         scale=float(a[8]) if len(a) > 8 else 1.0)
