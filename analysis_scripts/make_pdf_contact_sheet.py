"""Build a contact sheet from rendered PDF QA pages."""

from __future__ import annotations

import argparse
from pathlib import Path

from PIL import Image, ImageDraw


ROOT = Path(__file__).resolve().parents[1]
QA_DIR = ROOT / "09_pdf_qa"
OUT = QA_DIR / "contact_sheet.png"


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--pattern",
        action="append",
        dest="patterns",
        help="QA_DIR glob pattern. May be passed multiple times.",
    )
    parser.add_argument("--out", default=str(OUT), help="Output contact-sheet path.")
    args = parser.parse_args()

    if args.patterns:
        pages = []
        for pattern in args.patterns:
            pages.extend(sorted(QA_DIR.glob(pattern)))
    else:
        main_pages = sorted(QA_DIR.glob("main_page-*.png"))
        supplemental_pages = sorted(QA_DIR.glob("supp_final_page-*.png"))
        if not supplemental_pages:
            supplemental_pages = sorted(QA_DIR.glob("supp2_page-*.png"))
        if not supplemental_pages:
            supplemental_pages = sorted(QA_DIR.glob("supp_page-*.png"))
        pages = main_pages + supplemental_pages

    if not pages:
        raise SystemExit("no QA pages matched")

    thumbs = []
    for path in pages:
        image = Image.open(path).convert("RGB")
        image.thumbnail((360, 480))
        canvas = Image.new("RGB", (380, 530), "white")
        canvas.paste(image, ((380 - image.width) // 2, 20))
        ImageDraw.Draw(canvas).text((12, 500), path.name, fill=(0, 0, 0))
        thumbs.append(canvas)

    cols = 3
    rows = (len(thumbs) + cols - 1) // cols
    sheet = Image.new("RGB", (cols * 380, rows * 530), (245, 245, 245))
    for idx, thumb in enumerate(thumbs):
        sheet.paste(thumb, ((idx % cols) * 380, (idx // cols) * 530))
    out = Path(args.out)
    if not out.is_absolute():
        out = QA_DIR / out
    sheet.save(out)
    print(out)


if __name__ == "__main__":
    main()
