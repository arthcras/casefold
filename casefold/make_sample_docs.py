#!/usr/bin/env python3
"""Generate the fictitious scanned documents in data/documents/ (images and image-only PDFs, so they need OCR).
Every page carries the banner "SPECIMEN - FICTITIOUS TEST DOCUMENT"; no real register, form or logo is imitated.
The generated files are committed; you only need this script to change them.

usage:  python3 casefold/make_sample_docs.py          # needs Pillow (pip install pillow)
"""
import os, random
from PIL import Image, ImageDraw, ImageFilter, ImageFont

HERE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
OUT = os.path.join(HERE, 'data', 'documents')
BANNER = 'SPECIMEN - FICTITIOUS TEST DOCUMENT (Casefold demo)'

DOCS = {
    ('nl-kalmora', 'D3', 'png'): [[
        'UITTREKSEL UBO-REGISTER (specimen)',
        'Kalmora Europe B.V.',
        '',
        'Nr  Uiteindelijk belanghebbende   Aard belang            Omvang',
        '1   R. Okkema                     middellijk, zeggenschap  25-50%',
        '    via Tidewater Holdings Ltd (Cyprus)',
        '2   I. Valtor                     middellijk eigendom      25-50%',
        '    via Seagrape Ventures Ltd. (Panama)',
        '',
        'Geen andere natuurlijke personen geregistreerd.',
        'Datum uittreksel: 20 oktober 2026.',
    ]],
}


def font(size):
    for p in ['/usr/share/fonts/truetype/dejavu/DejaVuSerif.ttf', '/Library/Fonts/Times New Roman.ttf', '/System/Library/Fonts/Supplemental/Times New Roman.ttf']:
        if os.path.exists(p):
            return ImageFont.truetype(p, size)
    return ImageFont.load_default()


def page(lines, seed):
    rnd = random.Random(seed)
    img = Image.new('L', (1654, 2339), 250)  # A4 at 200 dpi
    d = ImageDraw.Draw(img)
    d.rectangle([80, 60, 1574, 130], outline=120, width=3)
    d.text((110, 78), BANNER, fill=90, font=font(34))
    y = 220
    for i, l in enumerate(lines):
        d.text((140, y), l, fill=20, font=font(46 if i == 0 else 38))
        y += 78 if i == 0 else 62
    img = img.rotate(rnd.uniform(-0.8, 0.8), fillcolor=250, resample=Image.BICUBIC)
    noise = Image.effect_noise(img.size, 14).point(lambda v: 0 if v < 118 else 255)
    img = Image.composite(img, Image.new('L', img.size, 235), noise.point(lambda v: 255 if v else 255))
    return img.filter(ImageFilter.GaussianBlur(0.6))


def main():
    for (case, doc, ext), pages in DOCS.items():
        os.makedirs(os.path.join(OUT, case), exist_ok=True)
        imgs = [page(p, f'{case}{doc}{i}') for i, p in enumerate(pages)]
        path = os.path.join(OUT, case, f'{doc}.{ext}')
        if ext == 'pdf':
            imgs[0].save(path, 'PDF', resolution=200, save_all=True, append_images=imgs[1:])
        else:
            imgs[0].save(path, optimize=True)
        print(path, len(imgs), 'page(s)')


if __name__ == '__main__':
    main()
