import io
from PIL import Image, ImageDraw, ImageOps

def embed_logo_with_clear_zone(
    png_bytes: bytes,
    logo_bytes: bytes,
    logo_rel_size: float = 0.20,   # 0.10–0.25 empfohlen
    margin: float = 0.10,          # 0.06–0.15 empfohlen
    corner_radius: float = 0.20,   # 0.0–0.5 (relativ zur Logo-Kante)
    outline_px: int = 2            # dünner weißer Rand um den Clear-Zone-Körper
) -> bytes:
    """
    Betten ein Logo mittig ein und erzeugen eine runde weiße Clear-Zone (mit optionaler Outline).
    - logo_rel_size: Anteil an der kürzeren QR-Kante (Clamping auf 0.08..0.28)
    - margin: zusätzlicher Weißrand relativ zur Logo-Kante (Clamping auf 0.04..0.20)
    - corner_radius: Rundungsgrad (0..0.5) relativ zur Logo-Kante
    """
    # Sanfte Grenzen
    logo_rel_size = max(0.08, min(0.28, float(logo_rel_size)))
    margin = max(0.04, min(0.20, float(margin)))
    corner_radius = max(0.0, min(0.5, float(corner_radius)))
    outline_px = max(0, int(outline_px))

    base = Image.open(io.BytesIO(png_bytes)).convert("RGBA")
    logo = Image.open(io.BytesIO(logo_bytes)).convert("RGBA")

    W, H = base.size
    short = min(W, H)

    # Logo skalieren
    target = int(short * logo_rel_size)
    logo.thumbnail((target, target), Image.LANCZOS)
    lw, lh = logo.size

    # Position mittig
    x = (W - lw) // 2
    y = (H - lh) // 2

    # Clear-Zone-Box (Logo + Margin)
    m = int(min(lw, lh) * margin)
    cz_left   = max(0, x - m)
    cz_top    = max(0, y - m)
    cz_right  = min(W, x + lw + m)
    cz_bottom = min(H, y + lh + m)

    # Runde Maske für Clear-Zone
    cz_w = cz_right - cz_left
    cz_h = cz_bottom - cz_top
    r = int(min(cz_w, cz_h) * corner_radius)

    cz_img = Image.new("RGBA", (cz_w, cz_h), (0, 0, 0, 0))
    mask = Image.new("L", (cz_w, cz_h), 0)
    draw = ImageDraw.Draw(mask)
    # abgerundetes Rechteck
    draw.rounded_rectangle([0, 0, cz_w, cz_h], radius=r, fill=255)

    # Clear-Zone (weiß) auf Basisbild legen
    white_rect = Image.new("RGBA", (cz_w, cz_h), (255, 255, 255, 255))
    base.alpha_composite(white_rect, dest=(cz_left, cz_top), source=mask)

    # Optionale weiße Outline um die Clear-Zone (sorgt für „Halo“-Gefühl)
    if outline_px > 0:
        # Outline als leicht größerer Radius – nur Kontur
        outline_mask = Image.new("L", (cz_w, cz_h), 0)
        draw_o = ImageDraw.Draw(outline_mask)
        draw_o.rounded_rectangle([outline_px, outline_px, cz_w - outline_px, cz_h - outline_px],
                                 radius=max(0, r - outline_px), fill=255)
        outline = ImageOps.expand(Image.new("RGBA", (cz_w, cz_h), (255, 255, 255, 0)),
                                  border=outline_px, fill=(255, 255, 255, 255))
        # Wir erzeugen eine Kontur, indem wir den Innenbereich abziehen:
        inner_mask = Image.new("L", (cz_w + 2*outline_px, cz_h + 2*outline_px), 0)
        d2 = ImageDraw.Draw(inner_mask)
        d2.rounded_rectangle([outline_px, outline_px, cz_w + outline_px, cz_h + outline_px],
                             radius=r, fill=255)
        # Außen - Innen = Kontur
        kontur = Image.new("L", inner_mask.size, 0)
        d3 = ImageDraw.Draw(kontur)
        d3.rounded_rectangle([0, 0, cz_w + 2*outline_px, cz_h + 2*outline_px],
                             radius=r + outline_px, fill=255)
        kontur = ImageChops.difference(kontur, inner_mask)

        # Auf Zielgröße bringen und aufsetzen
        kontur = kontur.crop((0, 0, cz_w + 2*outline_px, cz_h + 2*outline_px))
        halo = Image.new("RGBA", (cz_w + 2*outline_px, cz_h + 2*outline_px), (255, 255, 255, 255))
        base.alpha_composite(halo, dest=(cz_left - outline_px, cz_top - outline_px), source=kontur)

    # Logo einsetzen
    base.alpha_composite(logo, dest=(x, y))

    out = io.BytesIO()
    base.save(out, format="PNG")
    return out.getvalue()
