#!/usr/bin/env python3
"""Put the example documents of examples/kalmora-from-documents/ next to the viewer, for "New client from documents".

  web/data/examples/structure_chart.pdf          the chart itself: the browser reads it (pdf.js), as structure_chart.py does
  web/data/examples/ubo_register_extract.png     the scan: the browser reads it with Tesseract compiled to WebAssembly (web/vendor/tesseract)

usage:  python3 casefold/export_examples.py
"""
import os, shutil

HERE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SRC = os.path.join(HERE, 'examples', 'kalmora-from-documents')
OUT = os.path.join(HERE, 'web', 'data', 'examples')


def main():
    os.makedirs(OUT, exist_ok=True)
    shutil.copy2(os.path.join(SRC, 'documents', 'structure_chart.pdf'), os.path.join(OUT, 'structure_chart.pdf'))
    shutil.copy2(os.path.join(SRC, 'documents', 'ubo_register_extract.png'), os.path.join(OUT, 'ubo_register_extract.png'))
    for old in ('ubo_register_extract.json',):
        if os.path.exists(os.path.join(OUT, old)):
            os.remove(os.path.join(OUT, old))
    print(f'examples for the viewer: structure_chart.pdf, ubo_register_extract.png -> {os.path.relpath(OUT, HERE)}')


if __name__ == '__main__':
    main()
