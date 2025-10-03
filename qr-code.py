# qr-code.py
# Streamlit-App: QR-Codes als PNG/SVG erzeugen – Logo (Overlay oder Clear-Zone/Halo),
# Badge unten mit dickem, verbundenem Außenrahmen und Autoskalierung des Badge-Texts.
# Micro-QR ist entfernt.

import io
import zipfile
import streamlit as st

st.set_page_config(page_title="QR-Code Generator", page_icon="🔳", layout="centered")

# segno absichern
try:
    import segno
    SEGNO_OK = True
except Exception as e:
    SEGNO_OK = False
    SEGNO_ERR = e

st.title("🔳 QR-Code Generator")
st.write("QR-Codes als **PNG** oder **SVG** – Farbe, Fehlerkorrektur, Rand, Logo (mit Clear-Zone/Halo) "
         "und **Badge** unten mit dickem, verbundenem Außenrahmen. Text skaliert automatisch ins Feld.")

def clamp(v, lo, hi):
    return max(lo, min(hi, v))

# -------------------------------
# Logo-Funktionen
# -------------------------------
def embed_logo_overlay(png_bytes: bytes, logo_bytes: bytes, logo_rel_size: float = 0.20) -> bytes:
    from PIL import Image
    base = Image.open(io.BytesIO(png_bytes)).convert("RGBA")
    logo = Image.open(io.BytesIO(logo_bytes)).convert("RGBA")

    W, H = base.size
    short = min(W, H)
    logo_rel_size = clamp(logo_rel_size, 0.05, 0.35)
    target = int(short * logo_rel_size)

    logo.thumbnail((target, target), Image.LANCZOS)
    lw, lh = logo.size
    pos = ((W - lw) // 2, (H - lh) // 2)

    base.paste(logo, pos, logo)
    out = io.BytesIO()
    base.save(out, format="PNG")
    return out.getvalue()

def embed_logo_with_clear_zone(
    png_bytes: bytes,
    logo_bytes: bytes,
    logo_rel_size: float = 0.20,
    margin: float = 0.10,
    corner_radius: float = 0.20,
    outline_px: int = 0
) -> bytes:
    from PIL import Image, ImageDraw, ImageChops
    base = Image.open(io.BytesIO(png_bytes)).convert("RGBA")
    logo = Image.open(io.BytesIO(logo_bytes)).convert("RGBA")

    W, H = base.size
    short = min(W, H)

    logo_rel_size = clamp(logo_rel_size, 0.08, 0.28)
    margin = clamp(margin, 0.04, 0.20)
    corner_radius = clamp(corner_radius, 0.0, 0.5)
    outline_px = max(0, int(outline_px))

    target = int(short * logo_rel_size)
    logo.thumbnail((target, target), Image.LANCZOS)
    lw, lh = logo.size
    x, y = (W - lw) // 2, (H - lh) // 2

    # Clear-Zone-Box
    m = int(min(lw, lh) * margin)
    cz_left, cz_top = clamp(x - m, 0, W), clamp(y - m, 0, H)
    cz_right, cz_bottom = clamp(x + lw + m, 0, W), clamp(y + lh + m, 0, H)
    cz_w, cz_h = max(1, cz_right - cz_left), max(1, cz_bottom - cz_top)
    r = int(min(cz_w, cz_h) * corner_radius)

    # Maske für Clear-Zone
    mask = Image.new("L", (cz_w, cz_h), 0)
    draw = ImageDraw.Draw(mask)
    draw.rounded_rectangle([0, 0, cz_w-1, cz_h-1], radius=r, fill=255)

    # Clear-Zone füllen
    white_rect = Image.new("RGBA", (cz_w, cz_h), (255, 255, 255, 255))
    base.paste(white_rect, (cz_left, cz_top), mask)

    # Optionaler Halo-Ring
    if outline_px > 0:
        outer = Image.new("L", (cz_w+2*outline_px, cz_h+2*outline_px), 0)
        inner = Image.new("L", (cz_w+2*outline_px, cz_h+2*outline_px), 0)
        d_outer = ImageDraw.Draw(outer)
        d_inner = ImageDraw.Draw(inner)
        d_outer.rounded_rectangle(
            [0,0,outer.size[0]-1, outer.size[1]-1],
            radius=r+outline_px, fill=255
        )
        d_inner.rounded_rectangle(
            [outline_px,outline_px,outline_px+cz_w-1,outline_px+cz_h-1],
            radius=r, fill=255
        )
        contour = ImageChops.subtract(outer, inner)
        halo = Image.new("RGBA", contour.size, (255,255,255,255))
        base.paste(halo, (cz_left-outline_px, cz_top-outline_px), contour)

    # Logo einfügen
    base.paste(logo, (x, y), logo)

    out = io.BytesIO()
    base.save(out, format="PNG")
    return out.getvalue()

# -------------------------------
# Badge unten + dicker, verbundener Außenrahmen
# -------------------------------
def add_label_frame_full_border(
    png_bytes: bytes,
    label_text: str,
    frame_bg: str = "#0B5FFF",
    text_color: str = "#FFFFFF",
    outer_border_px: int = 12,          # dicker Rahmen
    outer_border_color: str = "#0B5FFF",
    pad_ratio: float = 0.06,            # Abstand QR ↔ Innenkante Rahmen (relativ zur QR-Kante)
    label_height_ratio: float = 0.20,   # Höhe des Badges (relativ)
    gap_px: int = 0                     # Spalt QR ↔ Badge
) -> bytes:
    from PIL import Image, ImageDraw, ImageFont

    # QR laden
    qr_img = Image.open(io.BytesIO(png_bytes)).convert("RGBA")
    W, H = qr_img.size
    side = min(W, H)

    # Parameter clampen
    pad_ratio          = clamp(pad_ratio, 0.0, 0.25)
    label_height_ratio = clamp(label_height_ratio, 0.10, 0.40)
    outer_border_px    = max(0, int(outer_border_px))
    gap_px             = max(0, int(gap_px))

    pad_px  = int(side * pad_ratio)
    label_h = int(side * label_height_ratio)

    # Außenform: abgerundeter, gefüllter Rahmen + innen ausgeräumt → verbundener, dicker Rahmen
    outer_r = int(round(0.12 * (W + H) / 2))           # Außenradius (12% des Mittelmaßes)
    inner_r = max(0, outer_r - outer_border_px)        # Innenradius um Rahmenbreite kleiner

    total_w = W + 2*pad_px + 2*outer_border_px
    total_h = H + 2*pad_px + gap_px + label_h + 2*outer_border_px

    canvas = Image.new("RGBA", (total_w, total_h), (0, 0, 0, 0))
    draw   = ImageDraw.Draw(canvas)

    # 1) Außenrahmen vollflächig zeichnen
    draw.rounded_rectangle(
        [0, 0, total_w-1, total_h-1],
        radius=outer_r,
        fill=outer_border_color
    )

    # 2) Innenbereich weiß ausräumen
    inner_box = [
        outer_border_px, outer_border_px,
        total_w-1-outer_border_px, total_h-1-outer_border_px
    ]
    draw.rounded_rectangle(inner_box, radius=inner_r, fill=(255, 255, 255, 255))

    # 3) QR in den Innenbereich setzen
    inner_left, inner_top, inner_right, inner_bottom = inner_box
    qr_x = inner_left + pad_px
    qr_y = inner_top  + pad_px
    canvas.paste(qr_img, (qr_x, qr_y), qr_img)

    # 4) Badge unten – volle Innenbreite, oben gerade, unten mit Innenradius gerundet
    label_x0 = inner_left + pad_px
    label_x1 = inner_right - pad_px
    label_y0 = qr_y + H + gap_px
    label_y1 = min(inner_bottom - pad_px, label_y0 + label_h)

    badge_h_rect = (label_y1 - label_y0) + inner_r  # Platz für Rundung unten
    badge_img = Image.new("RGBA", (label_x1 - label_x0 + 1, badge_h_rect), (0, 0, 0, 0))
    bd = ImageDraw.Draw(badge_img)
    bd.rounded_rectangle(
        [0, 0, badge_img.width - 1, badge_img.height - 1],
        radius=inner_r,
        fill=frame_bg
    )
    # obere Kante begradigen (damit oben straight ist)
    cut_h = badge_h_rect - (label_y1 - label_y0)
    if cut_h > 0:
        bd.rectangle([0, 0, badge_img.width - 1, cut_h], fill=frame_bg)

    # Badge auf Canvas aufsetzen (so dass die untere Rundung mit der Innenrundung „fluchtet“)
    canvas.paste(badge_img, (label_x0, label_y0 - cut_h), badge_img)

    # 5) Text im Badge – mit Innen-Padding & Autoskalierung
    text = (label_text or "").strip()
    if text:
        try:
            base_size = max(14, int((label_y1 - label_y0) * 0.56))
            font = ImageFont.truetype("DejaVuSans-Bold.ttf", base_size)
        except Exception:
            font = ImageFont.load_default()

        draw2 = ImageDraw.Draw(canvas)

        def measure(tfont):
            if hasattr(draw2, "textbbox"):
                l0 = draw2.textbbox((0, 0), text, font=tfont)
                return (l0[2] - l0[0], l0[3] - l0[1])
            elif hasattr(tfont, "getbbox"):
                b = tfont.getbbox(text)
                return (b[2] - b[0], b[3] - b[1])
            else:
                return (draw2.textlength(text, font=tfont), getattr(tfont, "size", 12))

        pad_x = int((label_x1 - label_x0 + 1) * 0.04)
        pad_y = max(2, int((label_y1 - label_y0) * 0.10))
        max_w = (label_x1 - label_x0 + 1) - 2 * pad_x
        max_h = (label_y1 - label_y0) - 2 * pad_y

        tw, th = measure(font)
        attempts = 0
        while (tw > max_w or th > max_h) and attempts < 16:
            size = getattr(font, "size", 16)
            size = max(10, int(size * 0.92))
            try:
                font = ImageFont.truetype("DejaVuSans-Bold.ttf", size)
            except Exception:
                font = ImageFont.load_default()
            tw, th = measure(font)
            attempts += 1

        tx = label_x0 + (label_x1 - label_x0 + 1 - tw) // 2
        ty = label_y0 + (label_y1 - label_y0 - th) // 2
        draw2.text((tx, ty), text, fill=text_color, font=font)

    out = io.BytesIO()
    canvas.save(out, format="PNG")
    return out.getvalue()

# -------------------------------
# Sidebar-Einstellungen
# -------------------------------
with st.sidebar:
    st.header("⚙️ Einstellungen")
    ecc = st.selectbox("Fehlerkorrektur", ["L","M","Q","H"], index=3, help="Für Logos ideal: Q/H.")
    scale = st.slider("Skalierung", 2, 20, 10)
    border = st.slider("Rand (Quiet Zone)", 0, 12, 4)
    dark = st.color_picker("Dunkel (Module)", "#000000")
    light = st.color_picker("Hell (Hintergrund)", "#FFFFFF")
    fmt = st.radio("Format", ["PNG","SVG"], horizontal=True)
    st.caption("💡 Für zuverlässiges Scannen: ECC Q/H, Rand ≥ 4, Light = #FFFFFF.")

if not SEGNO_OK:
    st.error(f"`segno` fehlt: {SEGNO_ERR}")
    st.stop()

# -------------------------------
# UI
# -------------------------------
preset_labels = [
    "Kein Badge",
    "Scan mich",
    "Lies mich",
    "Jetzt öffnen",
    "Eigener Text …",
]

tab_single, tab_batch = st.tabs(["Einzeln","Batch (CSV)"])

with tab_single:
    st.subheader("Einzel-QR")
    data = st.text_area("Inhalt", placeholder="https://example.org")

    # Logo-Optionen
    st.markdown("**Logo (optional)**")
    c1, c2 = st.columns(2)
    with c1:
        logo_file = st.file_uploader("Logo (PNG)", type=["png"])
        logo_scale = st.slider("Logo-Größe (%)", 8, 28, 20) / 100.0
    with c2:
        use_clear = st.checkbox("Clear-Zone unter Logo")
        cz_margin = st.slider("Clear-Zone-Rand (%)", 4,20,10) / 100.0
        cz_radius = st.slider("Eckenrundung (%)", 0,50,20) / 100.0
        halo_px = st.slider("Halo (px)", 0,8,0)

    # Badge + Rahmen
    st.markdown("**Badge & verbundener Außenrahmen**")
    rb1, rb2 = st.columns(2)
    with rb1:
        frame_choice = st.selectbox("Badge-Text", preset_labels, index=0)
        frame_bg = st.color_picker("Badge-Farbe", "#0B5FFF")
        outer_border_px = st.slider("Außenrahmen (px)", 0, 48, 12)  # bis 48 px
    with rb2:
        text_color = st.color_picker("Text-Farbe", "#FFFFFF")
        outer_border_color = st.color_picker("Rahmen-Farbe", "#0B5FFF")
        custom_text = ""
        if frame_choice == "Eigener Text …":
            custom_text = st.text_input("Badge-Text (eigene Eingabe)", "Scan mich")

    ft1, ft2, ft3 = st.columns(3)
    with ft1:
        pad_ratio = st.slider("Abstand QR↔Rahmen innen (%)", 0, 20, 6) / 100.0
    with ft2:
        label_ratio = st.slider("Badge-Höhe (%)", 10, 40, 20) / 100.0
    with ft3:
        gap_px = st.slider("Abstand QR↔Badge (px)", 0, 20, 0)

    if st.button("QR erzeugen", disabled=not data):
        qr = segno.make(data, error=ecc)
        if fmt == "SVG":
            buf = io.BytesIO()
            qr.save(buf, kind="svg", scale=scale, border=border, dark=dark, light=light)
            st.download_button("⬇️ SVG", buf.getvalue(), "qrcode.svg", "image/svg+xml")
            st.image(qr.to_pil(scale=6), caption="Vorschau")
        else:
            buf = io.BytesIO()
            qr.save(buf, kind="png", scale=scale, border=border, dark=dark, light=light)
            png = buf.getvalue()

            # Logo
            if logo_file:
                if use_clear:
                    png = embed_logo_with_clear_zone(
                        png, logo_file.read(),
                        logo_rel_size=logo_scale, margin=cz_margin,
                        corner_radius=cz_radius, outline_px=halo_px
                    )
                else:
                    png = embed_logo_overlay(png, logo_file.read(), logo_rel_size=logo_scale)

            # Badge + verbundener Außenrahmen
            if frame_choice != "Kein Badge":
                label_text = {
                    "Scan mich": "Scan mich",
                    "Lies mich": "Lies mich",
                    "Jetzt öffnen": "Jetzt öffnen",
                    "Eigener Text …": (custom_text or "Scan mich"),
                }.get(frame_choice, "")
                png = add_label_frame_full_border(
                    png,
                    label_text=label_text,
                    frame_bg=frame_bg,
                    text_color=text_color,
                    outer_border_px=outer_border_px,
                    outer_border_color=outer_border_color,
                    pad_ratio=pad_ratio,
                    label_height_ratio=label_ratio,
                    gap_px=gap_px,
                )

            st.image(png, caption="QR-Code")
            st.download_button("⬇️ PNG", png, "qrcode.png", "image/png")

with tab_batch:
    st.subheader("Batch aus CSV")
    st.caption("CSV mit Spalte 'data' und optional 'filename'")
    file = st.file_uploader("CSV hochladen", type=["csv"])

    # Batch-Badge-Optionen (einheitlich)
    st.markdown("**Badge & Rahmen (Batch, optional)**")
    b1, b2 = st.columns(2)
    with b1:
        batch_use_badge = st.checkbox("Badge im Batch anwenden")
        batch_frame_bg = st.color_picker("Badge-Farbe (Batch)", "#0B5FFF")
        batch_outer_border_px = st.slider("Außenrahmen (px) (Batch)", 0, 48, 12)
    with b2:
        batch_text_color = st.color_picker("Text-Farbe (Batch)", "#FFFFFF")
        batch_outer_border_color = st.color_picker("Rahmen-Farbe (Batch)", "#0B5FFF")
        batch_label_text = st.text_input("Badge-Text (Batch)", "Scan mich")

    b3, b4, b5 = st.columns(3)
    with b3:
        batch_pad = st.slider("Abstand QR↔Rahmen innen (%) (Batch)", 0, 20, 6) / 100.0
    with b4:
        batch_label_h = st.slider("Badge-Höhe (%) (Batch)", 10, 40, 20) / 100.0
    with b5:
        batch_gap = st.slider("Abstand QR↔Badge (px) (Batch)", 0, 20, 0)

    if file:
        import pandas as pd
        raw = file.read().decode("utf-8")
        sep = ";" if raw.count(";")>raw.count(",") else ","
        df = pd.read_csv(io.StringIO(raw), sep=sep)
        st.dataframe(df.head())
        if "data" in df.columns and st.button("Batch generieren"):
            zbuf = io.BytesIO()
            with zipfile.ZipFile(zbuf,"w") as z:
                for i,row in df.iterrows():
                    val = str(row["data"])
                    name = str(row["filename"]) if "filename" in df and pd.notna(row["filename"]) else f"qr_{i+1}"

                    out = io.BytesIO()
                    qr = segno.make(val, error=ecc)
                    qr.save(out, kind="png", scale=scale, border=border, dark=dark, light=light)
                    png = out.getvalue()

                    if batch_use_badge:
                        png = add_label_frame_full_border(
                            png,
                            label_text=batch_label_text,
                            frame_bg=batch_frame_bg,
                            text_color=batch_text_color,
                            outer_border_px=batch_outer_border_px,
                            outer_border_color=batch_outer_border_color,
                            pad_ratio=batch_pad,
                            label_height_ratio=batch_label_h,
                            gap_px=batch_gap,
                        )

                    z.writestr(f"{name}.png", png)
            zbuf.seek(0)
            st.download_button("⬇️ ZIP", zbuf, "qr_batch.zip", "application/zip")
