# qr-code.py
# Streamlit-App: QR-Codes als PNG/SVG erzeugen – optional mit Logo (Overlay oder Clear-Zone/Halo)
# NEU: Rahmen/Badge (Scan mich, Lies mich, eigener Text) mit Farbwahl
# HINWEIS: Micro-QR entfernt.

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
st.write("Erzeuge QR-Codes als **PNG** oder **SVG** – Farbe, Fehlerkorrektur, Rand, Logo (mit Clear-Zone/Halo) und **Rahmen/Badge** (z. B. „Scan mich“).")

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

    # Halo-Ring
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
# Rahmen/Badge-Funktion
# -------------------------------
def add_label_frame(
    png_bytes: bytes,
    label_text: str,
    frame_bg: str = "#000000",
    text_color: str = "#FFFFFF",
    pad_ratio: float = 0.06,       # Außenabstand um den QR (relativ zur QR-Kante)
    label_height_ratio: float = 0.20,  # Höhe der Label-Fläche unten (relativ zur QR-Kante)
    corner_radius_ratio: float = 0.10, # Rundung außen (relativ zur kürzeren Kante)
    outline_px: int = 0,               # optionaler Außenrahmen
    outline_color: str = None          # Farbe des Außenrahmens
) -> bytes:
    """
    Erzeugt unterhalb des QR-Codes eine farbige Label-Fläche mit Text.
    """
    from PIL import Image, ImageDraw, ImageFont

    # Laden
    qr_img = Image.open(io.BytesIO(png_bytes)).convert("RGBA")
    W, H = qr_img.size
    side = min(W, H)

    # Clamp und Umrechnungen
    pad_ratio = clamp(pad_ratio, 0.0, 0.25)
    label_height_ratio = clamp(label_height_ratio, 0.10, 0.35)
    corner_radius_ratio = clamp(corner_radius_ratio, 0.0, 0.25)

    pad_px = int(side * pad_ratio)
    label_h = int(side * label_height_ratio)
    outer_w = W + 2 * pad_px
    outer_h = H + 2 * pad_px + label_h
    r = int(min(outer_w, outer_h) * corner_radius_ratio)

    # Leinwand (weiß, damit QR-Light in Weiß „neutral“ bleibt)
    canvas = Image.new("RGBA", (outer_w, outer_h), (255, 255, 255, 255))
    draw = ImageDraw.Draw(canvas)

    # Optionaler Außenrahmen (Outline)
    if outline_px and outline_px > 0:
        oc = outline_color or frame_bg
        draw.rounded_rectangle(
            [0, 0, outer_w-1, outer_h-1],
            radius=r,
            outline=oc,
            width=outline_px,
            fill=None
        )

    # Label-Fläche (unten) – volle Breite, runde Ecken nur unten
    # Trick: abgerundetes Rechteck über gesamte Fläche + weiße Überdeckung oben
    label_rect = Image.new("RGBA", (outer_w, label_h + r), (0, 0, 0, 0))
    ld = ImageDraw.Draw(label_rect)
    ld.rounded_rectangle([0, 0, outer_w-1, label_h + r - 1], radius=r, fill=frame_bg)

    # Obere Kante der Label-Fläche horizontal abschneiden (damit nur unten rund bleibt)
    strip = Image.new("RGBA", (outer_w, r), (255, 255, 255, 255))
    label_rect.paste(strip, (0, 0), strip)

    # Auf Canvas platzieren
    label_y = outer_h - (label_h + r)
    canvas.paste(label_rect, (0, label_y), label_rect)

    # QR aufsetzen (oberhalb der Label-Fläche)
    canvas.paste(qr_img, (pad_px, pad_px), qr_img)

    # Text auf Label
    text = (label_text or "").strip()
    if text:
        # Font wählen (Fallback: Default)
        try:
            # Versuche DejaVu Sans (häufig in vielen Umgebungen vorhanden)
            font_size = max(12, int(label_h * 0.50))
            font = ImageFont.truetype("DejaVuSans-Bold.ttf", font_size)
        except Exception:
            font = ImageFont.load_default()

        # Dynamische Skalierung, damit Text reinpasst
        max_w = int(outer_w * 0.92)
        max_h = int(label_h * 0.80)
        if hasattr(font, "getbbox"):
            tb = font.getbbox(text)
            tw, th = tb[2] - tb[0], tb[3] - tb[1]
        else:
            tw, th = draw.textlength(text, font=font), font.size

        # ggf. Font kleiner machen
        attempts = 0
        while (tw > max_w or th > max_h) and attempts < 10:
            size = getattr(font, "size", 16)
            size = max(10, int(size * 0.92))
            try:
                font = ImageFont.truetype("DejaVuSans-Bold.ttf", size)
            except Exception:
                font = ImageFont.load_default()
            if hasattr(font, "getbbox"):
                tb = font.getbbox(text)
                tw, th = tb[2] - tb[0], tb[3] - tb[1]
            else:
                tw, th = draw.textlength(text, font=font), font.size
            attempts += 1

        tx = (outer_w - tw) // 2
        ty = label_y + (label_h - th) // 2 + int(r * 0.15)  # optische Zentrierung
        draw.text((tx, ty), text, fill=text_color, font=font)

    # Ausgabe
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
    st.caption("💡 Hoher Kontrast & Rand ≥4 verbessern die Scan-Qualität. Für Logos **ECC Q/H**, Light = #FFFFFF.")

if not SEGNO_OK:
    st.error(f"`segno` fehlt: {SEGNO_ERR}")
    st.stop()

# -------------------------------
# Tabs
# -------------------------------
preset_labels = [
    "Kein Rahmen/Badge",
    "Label unten: Scan mich",
    "Label unten: Lies mich",
    "Label unten: Jetzt öffnen",
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

    # Rahmen/Badge-Optionen
    st.markdown("**Rahmen/Badge**")
    rb1, rb2 = st.columns(2)
    with rb1:
        frame_choice = st.selectbox("Vorlage", preset_labels, index=0)
        frame_bg = st.color_picker("Badge-Farbe", "#0B5FFF")
    with rb2:
        text_color = st.color_picker("Text-Farbe", "#FFFFFF")
        custom_text = ""
        if frame_choice == "Eigener Text …":
            custom_text = st.text_input("Badge-Text", "Scan mich")

    # Feintuning Rahmen
    ft1, ft2, ft3 = st.columns(3)
    with ft1:
        pad_ratio = st.slider("Außenabstand (%)", 0, 20, 6) / 100.0
    with ft2:
        label_ratio = st.slider("Label-Höhe (%)", 10, 35, 20) / 100.0
    with ft3:
        outer_radius = st.slider("Außen-Ecken (%)", 0, 25, 10) / 100.0
    outline_px = st.slider("Außenrahmen (px)", 0, 6, 0)
    outline_color = st.color_picker("Außenrahmen-Farbe", "#0B5FFF")

    if st.button("QR erzeugen", disabled=not data):
        # 1) QR bauen
        qr = segno.make(data, error=ecc)  # Micro-QR entfernt
        if fmt=="SVG":
            buf = io.BytesIO()
            qr.save(buf, kind="svg", scale=scale, border=border, dark=dark, light=light)
            st.download_button("⬇️ SVG", buf.getvalue(), "qrcode.svg", "image/svg+xml")
            st.image(qr.to_pil(scale=6), caption="Vorschau")
        else:
            buf = io.BytesIO()
            # PNG mit Weiß als Light empfohlen (für saubere Badge/Label-Kanten)
            qr.save(buf, kind="png", scale=scale, border=border, dark=dark, light=light)
            png = buf.getvalue()

            # 2) Logo (optional)
            if logo_file:
                if use_clear:
                    png = embed_logo_with_clear_zone(
                        png, logo_file.read(),
                        logo_rel_size=logo_scale, margin=cz_margin,
                        corner_radius=cz_radius, outline_px=halo_px
                    )
                else:
                    png = embed_logo_overlay(png, logo_file.read(), logo_rel_size=logo_scale)

            # 3) Rahmen/Badge anwenden
            if frame_choice != "Kein Rahmen/Badge":
                label_map = {
                    "Label unten: Scan mich": "Scan mich",
                    "Label unten: Lies mich": "Lies mich",
                    "Label unten: Jetzt öffnen": "Jetzt öffnen",
                    "Eigener Text …": (custom_text or "Scan mich"),
                }
                label_text = label_map.get(frame_choice, "")
                png = add_label_frame(
                    png,
                    label_text=label_text,
                    frame_bg=frame_bg,
                    text_color=text_color,
                    pad_ratio=pad_ratio,
                    label_height_ratio=label_ratio,
                    corner_radius_ratio=outer_radius,
                    outline_px=outline_px,
                    outline_color=outline_color
                )

            st.image(png, caption="QR-Code")
            st.download_button("⬇️ PNG", png, "qrcode.png", "image/png")

with tab_batch:
    st.subheader("Batch aus CSV")
    st.caption("CSV mit Spalte 'data' und optional 'filename'")
    file = st.file_uploader("CSV hochladen", type=["csv"])
    # Batch-Rahmen/Badge-Optionen (einheitlich für alle)
    st.markdown("**Rahmen/Badge (Batch, optional)**")
    b1, b2 = st.columns(2)
    with b1:
        batch_use_badge = st.checkbox("Badge im Batch anwenden")
        batch_frame_bg = st.color_picker("Badge-Farbe (Batch)", "#0B5FFF")
    with b2:
        batch_text_color = st.color_picker("Text-Farbe (Batch)", "#FFFFFF")
        batch_label_text = st.text_input("Badge-Text (Batch)", "Scan mich")
    b3, b4, b5 = st.columns(3)
    with b3:
        batch_pad = st.slider("Außenabstand (%) (Batch)", 0, 20, 6) / 100.0
    with b4:
        batch_label_h = st.slider("Label-Höhe (%) (Batch)", 10, 35, 20) / 100.0
    with b5:
        batch_outer_r = st.slider("Außen-Ecken (%) (Batch)", 0, 25, 10) / 100.0
    batch_outline_px = st.slider("Außenrahmen (px) (Batch)", 0, 6, 0)
    batch_outline_color = st.color_picker("Außenrahmen-Farbe (Batch)", "#0B5FFF")

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

                    # QR erzeugen
                    out = io.BytesIO()
                    qr = segno.make(val, error=ecc)
                    qr.save(out, kind="png", scale=scale, border=border, dark=dark, light=light)
                    png = out.getvalue()

                    # Badge (optional, einheitlich)
                    if batch_use_badge:
                        png = add_label_frame(
                            png,
                            label_text=batch_label_text,
                            frame_bg=batch_frame_bg,
                            text_color=batch_text_color,
                            pad_ratio=batch_pad,
                            label_height_ratio=batch_label_h,
                            corner_radius_ratio=batch_outer_r,
                            outline_px=batch_outline_px,
                            outline_color=batch_outline_color
                        )

                    z.writestr(f"{name}.png", png)
            zbuf.seek(0)
            st.download_button("⬇️ ZIP", zbuf, "qr_batch.zip", "application/zip")
