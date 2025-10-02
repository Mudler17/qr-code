# qr-code.py
# Streamlit-App: QR-Codes als PNG/SVG erzeugen – optional mit Logo (Overlay oder Clear-Zone/Halo)
# Robust gegen fehlende Pakete: zeigt Fehler in der UI statt White Screen.

import io
import zipfile
import streamlit as st

st.set_page_config(page_title="QR-Code Generator", page_icon="🔳", layout="centered")

# --- Sichere segno-Initialisierung (verhindert White Screen) ---
try:
    import segno
    SEGNO_OK = True
except Exception as e:
    SEGNO_OK = False
    SEGNO_ERR = e

st.title("🔳 QR-Code Generator")
st.write("Erzeuge QR-Codes als **PNG** oder **SVG** – inkl. Farbe, Fehlerkorrektur, Rand, Größe und optionalem Logo (mit **Clear Zone/Halo**).")

# Sofortige Smoke-Info, damit man nie einen leeren Screen sieht
st.info("App geladen. Wenn unten nichts passiert, aktiviere '🐞 Debug-Ausgaben' in der Sidebar.")

def clamp(val, lo, hi):
    return max(lo, min(hi, val))

# =========================
# Logo-Funktionen (Lazy-PIL)
# =========================
def _lazy_pil():
    try:
        from PIL import Image, ImageDraw, ImageOps, ImageChops
        return Image, ImageDraw, ImageOps, ImageChops, None
    except Exception as pil_err:
        return None, None, None, None, pil_err

def embed_logo_overlay(png_bytes: bytes, logo_bytes: bytes, logo_rel_size: float = 0.20) -> bytes:
    """Logo einfach mittig aufsetzen (ohne Freiraum)."""
    Image, _, _, _, pil_err = _lazy_pil()
    if pil_err:
        st.error(f"Pillow (PIL) nicht verfügbar: {pil_err}\nBitte `pillow` in requirements.txt aufnehmen.")
        return png_bytes  # Fallback: Original zurückgeben

    base = Image.open(io.BytesIO(png_bytes)).convert("RGBA")
    logo = Image.open(io.BytesIO(logo_bytes)).convert("RGBA")

    W, H = base.size
    short = min(W, H)

    logo_rel_size = clamp(float(logo_rel_size), 0.05, 0.35)
    target = int(short * logo_rel_size)

    logo.thumbnail((target, target), Image.LANCZOS)
    lw, lh = logo.size

    x = (W - lw) // 2
    y = (H - lh) // 2

    base.alpha_composite(logo, dest=(x, y))
    out = io.BytesIO()
    base.save(out, format="PNG")
    return out.getvalue()

def embed_logo_with_clear_zone(
    png_bytes: bytes,
    logo_bytes: bytes,
    logo_rel_size: float = 0.20,   # Anteil an kürzerer QR-Kante
    margin: float = 0.10,          # zusätzlicher Weißrand relativ zur Logo-Kante
    corner_radius: float = 0.20,   # 0..0.5, Rundungen für die Clear-Zone
    outline_px: int = 0            # optionaler weißer Halo (Kontur) um Clear-Zone
) -> bytes:
    """
    Logo mittig einbetten und darunter eine weiße Clear-Zone ausspart.
    Empfohlen: ECC Q/H, Rand ≥ 4, light='#FFFFFF' beim QR-Render.
    """
    Image, ImageDraw, ImageOps, ImageChops, pil_err = _lazy_pil()
    if pil_err:
        st.error(f"Pillow (PIL) nicht verfügbar: {pil_err}\nBitte `pillow` in requirements.txt aufnehmen.")
        return png_bytes  # Fallback

    # Grenzen
    logo_rel_size = clamp(float(logo_rel_size), 0.08, 0.28)
    margin = clamp(float(margin), 0.04, 0.20)
    corner_radius = clamp(float(corner_radius), 0.0, 0.5)
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
    cz_left   = clamp(x - m, 0, W)
    cz_top    = clamp(y - m, 0, H)
    cz_right  = clamp(x + lw + m, 0, W)
    cz_bottom = clamp(y + lh + m, 0, H)

    cz_w = max(1, cz_right - cz_left)
    cz_h = max(1, cz_bottom - cz_top)
    r = int(min(cz_w, cz_h) * corner_radius)

    # Maske mit abgerundeten Ecken
    mask = Image.new("L", (cz_w, cz_h), 0)
    draw = ImageDraw.Draw(mask)
    draw.rounded_rectangle([0, 0, cz_w - 1, cz_h - 1], radius=r, fill=255)

    # Clear-Zone weiß füllen
    white_rect = Image.new("RGBA", (cz_w, cz_h), (255, 255, 255, 255))
    base.alpha_composite(white_rect, dest=(cz_left, cz_top), source=mask)

    # Optionaler Halo-Ring um die Clear-Zone
    if outline_px > 0:
        outer = Image.new("L", (cz_w + 2*outline_px, cz_h + 2*outline_px), 0)
        inner = Image.new("L", (cz_w + 2*outline_px, cz_h + 2*outline_px), 0)
        d_outer = ImageDraw.Draw(outer)
        d_inner = ImageDraw.Draw(inner)
        d_outer.rounded_rectangle(
            [0, 0, cz_w + 2*outline_px - 1, cz_h + 2*outline_px - 1],
            radius=r + outline_px, fill=255
        )
        d_inner.rounded_rectangle(
            [outline_px, outline_px, cz_w + outline_px - 1, cz_h + outline_px - 1],
            radius=r, fill=255
        )
        contour = ImageChops.subtract(outer, inner)  # Außen - Innen = Ring
        halo = Image.new("RGBA", contour.size, (255, 255, 255, 255))
        base.alpha_composite(halo, dest=(cz_left - outline_px, cz_top - outline_px), source=contour)

    # Logo einlegen
    base.alpha_composite(logo, dest=(x, y))

    out = io.BytesIO()
    base.save(out, format="PNG")
    return out.getvalue()

# =========================
# Sidebar: Einstellungen
# =========================
with st.sidebar:
    st.header("⚙️ Einstellungen")
    ecc = st.selectbox("Fehlerkorrektur", options=["L", "M", "Q", "H"], index=3, help="Für Logos ideal: Q/H.")
    scale = st.slider("Skalierung (PNG/SVG)", 2, 20, 10)
    border = st.slider("Rand / Quiet Zone", 0, 12, 4)
    dark = st.color_picker("Dunkel (Module)", "#000000")
    light = st.color_picker("Hell (Hintergrund)", "#FFFFFF")
    fmt = st.radio("Format", ["PNG", "SVG"], horizontal=True)
    micro = st.checkbox("Micro-QR versuchen (nur sehr kurze Daten)")
    debug = st.toggle("🐞 Debug-Ausgaben anzeigen", value=False)
    st.caption("💡 Hoher Kontrast & Rand ≥4 verbessern die Scan-Qualität. Für Logos **ECC Q/H**.")

# Wenn segno fehlt: sauber melden und stoppen (kein White Screen)
if not SEGNO_OK:
    st.error(f"`segno` konnte nicht importiert werden: {SEGNO_ERR}\n"
             "Bitte `segno>=1.6` in `requirements.txt` im Repo-Root eintragen und neu deployen.")
    st.stop()

tab_single, tab_batch = st.tabs(["Einzeln", "Batch (CSV)"])

# =========================
# Tab: Einzel-QR
# =========================
with tab_single:
    st.subheader("Einzel-QR")
    data = st.text_area("Inhalt (URL, Text, vCard, WLAN-String …)", placeholder="https://example.org", height=100)

    col1, col2 = st.columns(2)
    with col1:
        logo_file = st.file_uploader("Optional: Logo (PNG, transparent empfohlen)", type=["png"], accept_multiple_files=False)
        logo_scale = st.slider("Logo-Größe", 8, 28, 20, help="in % der kürzeren QR-Kante")
    with col2:
        use_clear_zone = st.checkbox("Freie Zone (Clear-Zone) unter Logo")
        clear_zone_margin = st.slider("Clear-Zone-Rand", 4, 20, 10, help="in % der Logo-Kante (zusätzlich)")
        corner_radius = st.slider("Eckenrundung (Clear-Zone)", 0, 50, 20, help="in % (0 = eckig, 50 = rund)")
        halo_outline = st.slider("Halo (weiße Kontur)", 0, 8, 0, help="in Pixeln")

    if st.button("QR-Code erzeugen", type="primary", disabled=not data):
        try:
            qr = segno.make(data, error=ecc, micro=micro)
            if fmt == "SVG":
                # SVG erzeugen (Logo-Einbettung nur für PNG)
                buf = io.BytesIO()
                qr.save(buf, kind="svg", scale=scale, border=border, dark=dark, light=light)
                svg_bytes = buf.getvalue()
                st.success("SVG erstellt.")
                st.download_button("⬇️ SVG herunterladen", data=svg_bytes, file_name="qrcode.svg", mime="image/svg+xml")
                st.write("Vorschau (rasterisiert):")
                st.image(qr.to_pil(scale=6, border=2), caption="Vorschau (Export ist SVG)")
            else:
                # PNG (weißes light empfohlen, damit Clear-Zone sichtbar bleibt)
                out = io.BytesIO()
                qr.save(out, kind="png", scale=scale, border=border, dark=dark, light=light)
                png_bytes = out.getvalue()

                if logo_file is not None:
                    logo_bytes = logo_file.read()
                    if use_clear_zone:
                        png_bytes = embed_logo_with_clear_zone(
                            png_bytes,
                            logo_bytes,
                            logo_rel_size=logo_scale / 100.0,
                            margin=clear_zone_margin / 100.0,
                            corner_radius=corner_radius / 100.0,
                            outline_px=halo_outline
                        )
                    else:
                        png_bytes = embed_logo_overlay(
                            png_bytes,
                            logo_bytes,
                            logo_rel_size=logo_scale / 100.0
                        )

                st.success("PNG erstellt.")
                st.image(png_bytes, caption="QR-Code", use_container_width=False)
                st.download_button("⬇️ PNG herunterladen", data=png_bytes, file_name="qrcode.png", mime="image/png")
        except Exception as e:
            if debug:
                st.exception(e)
            else:
                st.error("Es ist ein Fehler aufgetreten. Aktiviere 'Debug-Ausgaben' in der Sidebar.")

# =========================
# Tab: Batch (CSV)
# =========================
with tab_batch:
    st.subheader("Batch-Erstellung aus CSV")
    st.caption("CSV mit Spalte **data** (Pflicht) und optional **filename**. Trennzeichen: Komma oder Semikolon.")
    csv_file = st.file_uploader("CSV hochladen", type=["csv"])

    colb1, colb2 = st.columns(2)
    with colb1:
        allow_logo = st.checkbox("Logo bei PNG im Batch einbetten")
        batch_logo_scale = st.slider("Logo-Größe (Batch)", 8, 28, 20)
    with colb2:
        batch_clear_zone = st.checkbox("Freie Zone (Batch)")
        batch_clear_zone_margin = st.slider("Clear-Zone-Rand (Batch)", 4, 20, 10)
        batch_corner_radius = st.slider("Eckenrundung (Batch)", 0, 50, 20)
        batch_halo = st.slider("Halo (Batch)", 0, 8, 0)

    batch_logo = None
    if allow_logo:
        batch_logo = st.file_uploader("Batch-Logo (PNG)", type=["png"], key="batchlogo")

    if csv_file is not None:
        try:
            import pandas as pd
        except Exception as e_pd:
            st.error(f"`pandas` fehlt: {e_pd}\nBitte `pandas>=2.2` in requirements.txt aufnehmen.")
        else:
            try:
                raw = csv_file.read().decode("utf-8")
                sep = ";" if raw.count(";") > raw.count(",") else ","
                df = pd.read_csv(io.StringIO(raw), sep=sep)

                if "data" not in df.columns:
                    st.error("CSV benötigt mindestens eine Spalte namens 'data'.")
                else:
                    st.dataframe(df.head())
                    if st.button("Batch-QR-Codes generieren", type="primary"):
                        try:
                            zips = io.BytesIO()
                            with zipfile.ZipFile(zips, "w", zipfile.ZIP_DEFLATED) as zipf:
                                for idx, row in df.iterrows():
                                    value = str(row["data"])
                                    name = str(row["filename"]) if "filename" in df.columns and pd.notna(row["filename"]) else f"qr_{idx+1}"
                                    try:
                                        qr = segno.make(value, error=ecc, micro=micro)
                                        if fmt == "SVG":
                                            out = io.BytesIO()
                                            qr.save(out, kind="svg", scale=scale, border=border, dark=dark, light=light)
                                            zipf.writestr(f"{name}.svg", out.getvalue())
                                        else:
                                            out = io.BytesIO()
                                            qr.save(out, kind="png", scale=scale, border=border, dark=dark, light=light)
                                            png_bytes = out.getvalue()
                                            if allow_logo and batch_logo is not None:
                                                logo_bytes = batch_logo.read()
                                                if batch_clear_zone:
                                                    png_bytes = embed_logo_with_clear_zone(
                                                        png_bytes,
                                                        logo_bytes,
                                                        logo_rel_size=batch_logo_scale / 100.0,
                                                        margin=batch_clear_zone_margin / 100.0,
                                                        corner_radius=batch_corner_radius / 100.0,
                                                        outline_px=batch_halo
                                                    )
                                                else:
                                                    png_bytes = embed_logo_overlay(
                                                        png_bytes,
                                                        logo_bytes,
                                                        logo_rel_size=batch_logo_scale / 100.0
                                                    )
                                                # Logo-Stream zurückspulen
                                                batch_logo.seek(0)
                                            zipf.writestr(f"{name}.png", png_bytes)
                                    except Exception as e_row:
                                        zipf.writestr(f"ERROR_row_{idx+1}.txt", f"Fehler für '{name}': {e_row}")
                            zips.seek(0)
                            st.download_button("⬇️ ZIP herunterladen", data=zips, file_name="qr_batch.zip", mime="application/zip")
                        except Exception as e_zip:
                            if debug:
                                st.exception(e_zip)
                            else:
                                st.error("Batch-Export fehlgeschlagen. Aktiviere 'Debug-Ausgaben' in der Sidebar.")
            except Exception as e_csv:
                if debug:
                    st.exception(e_csv)
                else:
                    st.error("CSV konnte nicht verarbeitet werden. Aktiviere 'Debug-Ausgaben' in der Sidebar.")

st.markdown("---")
st.caption(
    "Tipps: Für Logos **ECC Q/H**, Rand ≥ 4, Logo 12–22 % der kürzeren Kante, Clear-Zone 6–12 %, "
    "rundere Clear-Zone (15–25 %) scannen oft zuverlässiger. Für PNG sollte **Hell/Light = #FFFFFF** sein."
)
