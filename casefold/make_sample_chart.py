#!/usr/bin/env python3
"""Draw the fictitious structure chart of the Kalmora group as a vector PDF, the way a client delivers one
(boxes for the parties, lines for ownership and control, a label on every line, arrows pointing to what is owned).
Every page carries the banner "SPECIMEN - FICTITIOUS TEST DOCUMENT"; no real company, register or form is imitated.
The generated file is committed; you only need this script to change it.

usage:  python3 casefold/make_sample_chart.py      # needs reportlab (pip install reportlab)
        -> examples/kalmora-from-documents/documents/structure_chart.pdf
"""
import os
from reportlab.lib.pagesizes import A4, landscape
from reportlab.pdfgen import canvas

HERE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
OUT = os.path.join(HERE, 'examples', 'kalmora-from-documents', 'documents', 'structure_chart.pdf')
W, H = landscape(A4)
BW, BH = 148, 40   # box size

# name, second line, centre x, centre y (points, origin bottom left)
BOXES = {
    'OKK': ('Ruben Okkema', 'person · Netherlands', 90, 470),
    'BRO': ('Lina Brouwer', 'person · Netherlands', 255, 470),
    'VAL': ('Ines Valtor', 'person · Curaçao', 435, 470),
    'DAS': ('Mara Dasilva', 'person · Netherlands', 600, 470),
    'HEN': ('Pieter Hendrikx', 'person · Netherlands', 760, 470),
    'TID': ('Tidewater Holdings Ltd', 'company · Cyprus', 180, 340),
    'SEA': ('Seagrape Ventures Ltd.', 'company · Panama', 435, 340),
    'STAK': ('Stichting Administratiekantoor Kalmora', 'foundation · Netherlands', 680, 340),
    'GRP': ('Kalmora Group Ltd', 'company · British Virgin Islands', 435, 215),
    'CLI': ('Kalmora Europe B.V.', 'company · Netherlands · client', 435, 95),
}
# from, to, label lines, dashed, route (bend points after the start), label side ('r' or 'l')
LINES = [
    ('OKK', 'TID', ['60%'], False, None, 'l'),
    ('BRO', 'TID', ['40%'], False, None, 'r'),
    ('VAL', 'SEA', ['100%', '(30% via a nominee)'], False, None, 'r'),
    ('DAS', 'STAK', ['depositary receipts 100%,', 'no votes'], False, None, 'l'),
    ('HEN', 'STAK', ['board, exercises', '100% of votes'], False, None, 'r'),
    ('TID', 'GRP', ['40%'], False, [(180, 268), (400, 268), (400, 236)], 'r'),
    ('SEA', 'GRP', ['35%'], False, None, 'r'),
    ('STAK', 'GRP', ['25%'], False, [(680, 268), (470, 268), (470, 236)], 'r'),
    ('GRP', 'CLI', ['100%'], False, None, 'r'),
    ('BRO', 'GRP', ['veto', '(shareholders agreement art. 4)'], True, [(285, 215), (360, 215)], 'r'),
]


def arrow(c, p, q):
    import math
    ang = math.atan2(q[1] - p[1], q[0] - p[0])
    l, w = 9, 4
    pts = [q, (q[0] - l * math.cos(ang) + w * math.sin(ang), q[1] - l * math.sin(ang) - w * math.cos(ang)),
           (q[0] - l * math.cos(ang) - w * math.sin(ang), q[1] - l * math.sin(ang) + w * math.cos(ang))]
    path = c.beginPath(); path.moveTo(*pts[0]); path.lineTo(*pts[1]); path.lineTo(*pts[2]); path.close()
    c.drawPath(path, stroke=0, fill=1)


def main():
    os.makedirs(os.path.dirname(OUT), exist_ok=True)
    c = canvas.Canvas(OUT, pagesize=(W, H))
    c.setTitle('Structure chart Kalmora group (specimen)'); c.setAuthor('Casefold demo (fictitious)')
    c.setFont('Helvetica-Bold', 9); c.setFillColorRGB(.75, .1, .1)
    c.drawString(30, H - 22, 'SPECIMEN - FICTITIOUS TEST DOCUMENT (Casefold demo)')
    c.setFillColorRGB(0, 0, 0); c.setFont('Helvetica-Bold', 14)
    c.drawString(30, H - 45, 'Structure chart Kalmora group')
    c.setFont('Helvetica', 9)
    c.drawString(30, H - 60, 'Dated 2 October 2026. Verified against the registers by the trust office. Arrows point to the entity that is owned or controlled.')
    for k, (name, sub, x, y) in BOXES.items():
        c.setLineWidth(1.6 if k == 'CLI' else 1); c.setDash()
        c.rect(x - BW / 2, y - BH / 2, BW, BH, stroke=1, fill=0)
        size = 7.2 if len(name) > 28 else 10
        c.setFont('Helvetica-Bold', size); c.drawCentredString(x, y + 3, name)
        c.setFont('Helvetica', 8); c.drawCentredString(x, y - 11, sub)
    for a, b, label, dashed, route, side in LINES:
        if route:
            pts = [(BOXES[a][2] + (30 if a == 'BRO' else 0), BOXES[a][3] - BH / 2), *route]
        else:
            pts = [(BOXES[a][2], BOXES[a][3] - BH / 2), (BOXES[b][2], BOXES[b][3] + BH / 2)]
        c.setLineWidth(1); c.setDash(4, 3) if dashed else c.setDash()
        for p, q in zip(pts, pts[1:]):
            c.line(p[0], p[1], q[0], q[1])
        c.setDash(); arrow(c, pts[-2], pts[-1])
        p, q = (pts[0], pts[1])
        f = 0.62 if a == 'BRO' else 0.5
        mx, my = p[0] + (q[0] - p[0]) * f, p[1] + (q[1] - p[1]) * f
        c.setFont('Helvetica-Oblique', 8)
        for i, t in enumerate(label):
            y = my + 4 - i * 10
            if side == 'r':
                c.drawString(mx + 6, y, t)
            else:
                c.drawRightString(mx - 6, y, t)
    c.setFont('Helvetica', 7.5)
    c.drawString(30, 30, 'Client: Kalmora Europe B.V. · prepared for the client acceptance file of the trust office · all names are fictitious')
    c.showPage(); c.save()
    print(OUT)


if __name__ == '__main__':
    main()
