"""Generate a generic sample banner for testing the vision pipeline.

Legible headline / performance / risk-o-meter, but a deliberately TINY, low-contrast
mandatory warning at the bottom — the case plain OCR flattens into 'present'.
"""
from pathlib import Path

from PIL import Image, ImageDraw, ImageFont

OUT = Path(__file__).resolve().parent.parent / "samples" / "sample_banner.png"


def font(size, bold=False):
    for name in (("arialbd.ttf" if bold else "arial.ttf"), "DejaVuSans.ttf"):
        try:
            return ImageFont.truetype(name, size)
        except OSError:
            continue
    return ImageFont.load_default()


def main():
    img = Image.new("RGB", (1000, 600), "white")
    d = ImageDraw.Draw(img)
    d.text((60, 55), "[AMC] Flexi Cap Fund", fill="black", font=font(54, True))
    d.text((60, 135), "An open-ended dynamic equity scheme", fill=(90, 90, 90), font=font(24))
    d.text((60, 235), "5-Year CAGR: 12.4%", fill=(0, 95, 45), font=font(46, True))
    d.text((60, 320), "Start a SIP today.", fill="black", font=font(30))

    # A visible, labelled risk-o-meter element.
    d.rectangle((650, 230, 940, 340), outline=(200, 120, 0), width=3)
    d.text((672, 250), "RISK-O-METER", fill=(120, 120, 120), font=font(18))
    d.text((700, 285), "VERY HIGH", fill=(200, 60, 0), font=font(30, True))

    # The mandatory 14-word warning — present, but tiny and low-contrast (near-illegible).
    warning = ("Mutual Fund investments are subject to market risks, read all scheme related "
               "documents carefully. Past performance may or may not be sustained in future.")
    d.text((60, 582), warning, fill=(206, 206, 206), font=font(7))

    OUT.parent.mkdir(parents=True, exist_ok=True)
    img.save(OUT)
    print(f"wrote {OUT}")


if __name__ == "__main__":
    main()
