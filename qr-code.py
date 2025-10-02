def embed_logo_with_clear_zone(
    png_bytes: bytes,
    logo_bytes: bytes,
    logo_rel_size: float = 0.20,   # 0.10–0.25 empfohlen
    margin: float = 0.10,          # 0.06–0.15 empfohlen
    corner_radius: float = 0.20,   # 0.0–0.5 (relativ zur Clear-Zone-Kante)
    outline_px: int = 0            # optionaler weißer Halo-Rand um die Clear-Zone
) -> bytes:
    # Clamping
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

    cz_w = cz_right - cz_left
    cz_h = cz_bottom - cz_top
    r = int(min(cz_w, cz_h) * corner_radius)

    # Maske mit abgerundeten Ecken
    mask = Image.new("L", (cz_w, cz_h), 0)
    draw = ImageDraw.Draw(mask)
    draw.rounded_rectangle([0, 0, cz_w, cz_h], radius=r, fill=255)

    # Clear-Zone weiß füllen
    white_rect = Image.new("RGBA", (cz_w, cz_h), (255, 255, 255, 255))
    base.alpha_composite(white_rect, dest=(cz_left, cz_top), source=mask)

    # Optionaler Halo (weiße Kontur um die Clear-Zone)
    if outline_px > 0:
        outer = Image.new("L", (cz_w + 2*outline_px, cz_h + 2*outline_px), 0)
        inner = Image.new("L", (cz_w + 2*outline_px, cz_h + 2*outline_px), 0)
        d_outer = ImageDraw.Draw(outer)
        d_inner = ImageDraw.Draw(inner)
        d_outer.rounded_rectangle([0, 0, cz_w + 2*outline_px - 1, cz_h + 2*outline_px - 1],
                                  radius=r + outline_px, fill=255)
        d_inner.rounded_rectangle([outline_px, outline_px, cz_w + outline_px - 1, cz_h + outline_px - 1],
                                  radius=r, fill=255)
        contour = ImageChops.subtract(outer, inner)
        halo = Image.new("RGBA", contour.size, (255, 255, 255, 255))
        base.alpha_composite(halo, dest=(cz_left - outline_px, cz_top - outline_px), source=contour)

    # Logo aufsetzen
    base.alpha_composite(logo, dest=(x, y))

    out = io.BytesIO()
    base.save(out, format="PNG")
    return out.getvalue()
