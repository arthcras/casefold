#!/usr/bin/env python3
"""Test fixture for law_ingest.py: a short PDF in the layout of a wetten.nl print, with four Wwft articles whose text was
read earlier (the real law comes from laws/sources/, see casefold/law_fetch.py). Also an image-only copy to test the OCR path."""
import os, subprocess
from reportlab.lib.pagesizes import A4
from reportlab.pdfgen import canvas
from textwrap import wrap
HERE = os.path.dirname(os.path.abspath(__file__))
OUT = os.path.join(HERE, 'fixtures')
ARTS = [
 ('2b', ['1. Een instelling neemt maatregelen om haar risico’s op witwassen en financieren van terrorisme vast te stellen en te beoordelen, waarbij de maatregelen in verhouding staan tot de aard en de omvang van de instelling.']),
 ('10c', ['1. Een instelling doet melding aan de Kamer van Koophandel van iedere discrepantie die zij aantreft tussen een gegeven omtrent een uiteindelijk belanghebbende dat zij verstrekt heeft gekregen uit het handelsregister, bedoeld in artikel 2 van de Handelsregisterwet 2007, en de informatie over die uiteindelijk belanghebbende waarover zij uit anderen hoofde beschikt.']),
 ('16', ['1. Een instelling meldt een verrichte of voorgenomen ongebruikelijke transactie onverwijld nadat het ongebruikelijke karakter van de transactie bekend is geworden, aan de Financiële inlichtingen eenheid.']),
 ('33', ['1. Een instelling die op grond van deze wet cliëntenonderzoek heeft verricht, legt op opvraagbare wijze de documenten en gegevens vast die zijn gebruikt voor de naleving van het bepaalde in artikel 3, tweede tot en met vierde lid.',
         '3. Een instelling bewaart de in het eerste en tweede lid bedoelde gegevens op toegankelijke wijze gedurende vijf jaar.']),
]
def main():
    os.makedirs(OUT, exist_ok=True)
    p = os.path.join(OUT, 'law-sample-nl.pdf')
    c = canvas.Canvas(p, pagesize=A4); y = 800
    c.setFont('Helvetica', 8); c.drawString(40, 820, 'wetten.nl - Regeling - Wet ter voorkoming van witwassen en financieren van terrorisme - BWBR0024282'); c.setFont('Helvetica', 11)
    for n, paras in ARTS:
        c.setFont('Helvetica-Bold', 12); c.drawString(40, y, f'Artikel {n}'); y -= 20; c.setFont('Helvetica', 11)
        for para in paras:
            for line in wrap(para, 95):
                c.drawString(40, y, line); y -= 15
            y -= 6
        y -= 10
    c.setFont('Helvetica', 8); c.drawString(40, 30, 'Pagina 1 van 1'); c.save()
    img = os.path.join(OUT, 'law-sample-nl-scan')
    subprocess.run(['pdftoppm', '-r', '200', '-png', '-singlefile', p, img], check=True)
    from PIL import Image
    Image.open(img + '.png').convert('RGB').save(os.path.join(OUT, 'law-sample-nl-scan.pdf')); os.remove(img + '.png')
    print('fixtures:', p, os.path.join(OUT, 'law-sample-nl-scan.pdf'))
if __name__ == '__main__':
    main()
