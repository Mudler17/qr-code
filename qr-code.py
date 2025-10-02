# qr-code.py
# Streamlit-App: QR-Codes als PNG/SVG erzeugen – optional mit Logo (Overlay oder Clear-Zone/Halo)

import io
import zipfile
import streamlit as st

st.set_page_config(page_title="QR-Code Generator", page_icon="🔳", layout="centered")

# segno absichern (sonst weißer Screen)
try:
    import segno
    SEGNO_OK = True
except Exception as e:
    SEGNO_OK = False
    SEGNO_ERR = e

st.title("🔳 QR-Code Generator")
st.write("Erzeuge QR-Codes als **PNG** oder **SVG** – inkl. Farbe, Fehlerkorrektur, Rand, Größe und optionalem Logo (mit **Clear Zone/Halo**).")

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
# Sidebar-Einstellungen
# -------------------------------
with st.sidebar:
    st.header("⚙️ Einstellungen")
    ecc = st.selectbox("Fehlerkorrektur", ["L","M","Q","H"], index=3)
    scale = st.slider("Skalierung", 2, 20, 10)
    border = st.slider("Rand", 0, 12, 4)
    dark = st.color_picker("Dunkel", "#000000")
    light = st.color_picker("Hell", "#FFFFFF")
    fmt = st.radio("Format", ["PNG","SVG"], horizontal=True)
    micro = st.checkbox("Micro-QR")
    st.caption("💡 Für Logos ECC Q/H, Rand ≥4, Light = #FFFFFF empfohlen.")

if not SEGNO_OK:
    st.error(f"`segno` fehlt: {SEGNO_ERR}")
    st.stop()

# -------------------------------
# Tabs
# -------------------------------
tab_single, tab_batch = st.tabs(["Einzeln","Batch (CSV)"])

with tab_single:
    st.subheader("Einzel-QR")
    data = st.text_area("Inhalt", placeholder="https://example.org")
    logo_file = st.file_uploader("Logo (PNG)", type=["png"])
    logo_scale = st.slider("Logo-Größe (%)", 8, 28, 20) / 100.0
    use_clear = st.checkbox("Clear-Zone unter Logo")
    cz_margin = st.slider("Clear-Zone-Rand (%)", 4,20,10) / 100.0
    cz_radius = st.slider("Eckenrundung (%)", 0,50,20) / 100.0
    halo_px = st.slider("Halo (px)", 0,8,0)

    if st.button("QR erzeugen", disabled=not data):
        qr = segno.make(data, error=ecc, micro=micro)
        if fmt=="SVG":
            buf = io.BytesIO()
            qr.save(buf, kind="svg", scale=scale, border=border, dark=dark, light=light)
            st.download_button("⬇️ SVG", buf.getvalue(), "qrcode.svg", "image/svg+xml")
            st.image(qr.to_pil(scale=6), caption="Vorschau")
        else:
            buf = io.BytesIO()
            qr.save(buf, kind="png", scale=scale, border=border, dark=dark, light=light)
            png = buf.getvalue()
            if logo_file:
                if use_clear:
                    png = embed_logo_with_clear_zone(png, logo_file.read(),
                        logo_rel_size=logo_scale, margin=cz_margin,
                        corner_radius=cz_radius, outline_px=halo_px)
                else:
                    png = embed_logo_overlay(png, logo_file.read(), logo_rel_size=logo_scale)
            st.image(png, caption="QR-Code")
            st.download_button("⬇️ PNG", png, "qrcode.png", "image/png")

with tab_batch:
    st.subheader("Batch aus CSV")
    st.caption("CSV mit Spalte 'data' und optional 'filename'")
    file = st.file_uploader("CSV hochladen", type=["csv"])
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
                    qr = segno.make(val, error=ecc, micro=micro)
                    qr.save(out, kind="png", scale=scale, border=border, dark=dark, light=light)
                    z.writestr(f"{name}.png", out.getvalue())
            zbuf.seek(0)
            st.download_button("⬇️ ZIP", zbuf, "qr_batch.zip", "application/zip")
