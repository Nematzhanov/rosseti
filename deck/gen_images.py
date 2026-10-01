"""Фирменная графика презентации: градиент обложки с узором и «волна» из линий (провода ЛЭП)."""
from pathlib import Path

import numpy as np
from PIL import Image, ImageDraw, ImageFilter

OUT = Path(__file__).resolve().parent / "img"
OUT.mkdir(exist_ok=True)
NAVY = np.array([6, 24, 58])
BLUE = (0, 90, 155)
rng = np.random.default_rng(7)


def overlay(w=1920, h=1080):
    """Тёмно-синий градиент сверху-слева + узор из коротких линий внизу (как фирменный паттерн)."""
    yy, xx = np.mgrid[0:h, 0:w]
    t = np.clip(1.15 - (xx / w * 0.55 + yy / h * 0.9), 0, 1)  # 1 у верхнего левого угла
    a = (t ** 1.4 * 235).astype(np.uint8)
    img = np.zeros((h, w, 4), np.uint8)
    img[..., :3] = NAVY
    img[..., 3] = a
    im = Image.fromarray(img, "RGBA")
    pat = Image.new("RGBA", (w * 2, h * 2), (0, 0, 0, 0))
    d = ImageDraw.Draw(pat)
    step = 22
    for gy in range(int(h * 2 * 0.45), h * 2, step):
        fade = (gy / (h * 2) - 0.45) / 0.55  # 0 -> 1 к низу
        for gx in range(0, w * 2, step):
            if rng.random() > 0.35 + 0.5 * fade:
                continue
            alpha = int(18 + 55 * fade * rng.random())
            if rng.random() < 0.5:
                d.line([(gx, gy), (gx + step * 0.8, gy)], fill=(255, 255, 255, alpha), width=2)
            else:
                d.line([(gx, gy), (gx, gy + step * 0.8)], fill=(255, 255, 255, alpha), width=2)
    pat = pat.resize((w, h), Image.LANCZOS)
    return Image.alpha_composite(im, pat)


def wave(color, alphas, w=2400, h=700, n=26, seed=3):
    """Пучок плавных линий, расходящихся веером, — «провода»."""
    r = np.random.default_rng(seed)
    S = 2
    im = Image.new("RGBA", (w * S, h * S), (0, 0, 0, 0))
    d = ImageDraw.Draw(im)
    x = np.linspace(0, w * S, 900)
    for i in range(n):
        k = i / (n - 1)
        phase = 0.35 * k
        amp = (0.16 + 0.16 * k) * h * S
        base = (0.66 - 0.2 * k) * h * S
        y = base + amp * np.sin(2 * np.pi * (x / (w * S)) * 0.9 + 1.2 + phase) \
            + 0.06 * h * S * np.sin(2 * np.pi * (x / (w * S)) * 2.3 + 3 * k)
        al = int(alphas[0] + (alphas[1] - alphas[0]) * (0.5 + 0.5 * np.sin(np.pi * k * 1.7)))
        d.line(list(zip(x, y)), fill=(*color, al), width=int(2 * S * (0.8 + 0.6 * r.random())), joint="curve")
    im = im.filter(ImageFilter.GaussianBlur(0.6)).resize((w, h), Image.LANCZOS)
    return im


overlay().save(OUT / "overlay.png")
wave((255, 255, 255), (40, 150)).save(OUT / "wave_white.png")
wave(BLUE, (45, 140)).save(OUT / "wave_blue.png")
print(sorted(p.name for p in OUT.iterdir()))
