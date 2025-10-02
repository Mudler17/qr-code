import io
import streamlit as st
import segno

st.set_page_config(page_title="QR-Code Generator", page_icon="🔳", layout="centered")
st.title("🔳 QR-Code Generator")
st.write("Erzeuge QR-Codes als **PNG** oder **SVG** – inkl. Farbe, Fehlerkorrektur, Rand, Größe und optionalem Logo (mit **Clear Zone**).")

# -----------------------
# Hilfsfunktionen (Logo)
# -----------------------
def _ensure_pillow():
    try:
        from PIL import Image  # noqa: F401
        return True
    except Exception:
        return False

def embed_logo_overlay(png_bytes: bytes, logo_bytes: bytes, logo_rel_size: float = 0.20) -> bytes:
    """Logo simpel mittig überlagern (ohne Freiraum)."""
    if not _ensure_pillow():
        st.warning("Pillow ist nicht installiert – Logo wird ignoriert.")
        return png_bytes

    from PIL import Image

    base = Image.open(io.BytesIO(png_bytes)).convert("RGBA")
    logo = Image.open(io.BytesIO(logo_bytes)).convert("RGBA")

    w, h = base.size
    short_side = min(w, h)
    logo_rel_size = max(0.05, min(0.35, float(logo_rel_size)))
    target = int(short_side * logo_rel_size)

    logo.thumbnail((target, target), Image.LANCZOS)
    lw, lh = logo.size
    pos = ((w - lw) // 2, (h - lh) // 2)

    base.alpha_composite(logo, dest=pos)
    out = io.BytesIO()
    base.save(out, format="PNG")
    return out.getvalue()

def embed_logo_with_clear_zone(png_bytes: bytes, logo_bytes: bytes, logo_rel_size: float = 0.20, margin: float = 0.10) -> bytes:
    """
    Logo mittig einbetten und eine 'freie Zone' (weiß) um das Logo schaffen.
    - logo_rel_size: 0.05–0.35 (relativ zur kürzeren Kante)
    - margin: zusätzlicher Weißrand um das Logo, z. B. 0.10 = 10%
    """
    if not _ensure_pillow():
        st.warning("Pillow ist nicht installiert – Logo wird ignoriert.")
        return png_bytes

    from PIL import Image, ImageDraw

    base = Image.open(io.BytesIO(png_bytes)).convert("RGBA")
    logo = Image.open(io.BytesIO(logo_bytes)).convert("RGBA")

    w, h = base.size
    short_side = min(w, h)
    logo_rel_size = max(0.05, min(0.35, float(logo_rel_size)))
    target = int(short_side * logo_rel_size)

    logo.thumbnail((target, target), Image.LANCZOS)
    lw, lh = logo.size
    pos = ((w - lw) // 2, (h - lh) // 2)

    # Freie (weiße) Zone um das Logo zeichnen
    margin_px = int(target * max(0.0, min(0.5, float(margin))))
    rect = [pos[0] - margin_px, pos[1] - margin_px, pos[0] + lw + margin_px, pos[1] + lh + margin_px]

    # Weißes Rechteck „ausschneiden“
    draw = ImageDraw.Draw(base)
    draw.rectangle(rect, fill="white")

    # Logo platzieren
    base.alpha_composite(logo, dest=pos)

    out = io.BytesIO()
    base.save(out, format="PNG")
    return out.getvalue()

# -----------------------
# Sidebar: Einstellungen
# -----------------------
with st.sidebar:
    st.header("⚙️ Einstellungen")
    ecc = st.selectbox("Fehlerkorrektur", options=["L", "M", "Q", "H"], index=3, help="Höher = robuster. Für Logo ideal: Q/H.")
    scale = st.slider("Skalierung (PNG/SVG)", 2, 20, 10)
    border = st.slider("Rand / Quiet Zone", 0, 12, 4)
    dark = st.color_picker("Dunkel (Module)", "#000000")
    light = st.color_picker("Hell (Hintergrund)", "#FFFFFF")
    fmt = st.radio("Format", ["PNG", "SVG"], horizontal=True)
    micro = st.checkbox("Micro-QR versuchen (nur sehr kurze Daten)")

    st.caption("💡 Tipp: Hoher Kontrast und Rand ≥4 verbessern die Scan-Qualität. Für Logos besser ECC **Q/H**.")

tab_single, tab_batch = st.tabs(["Einzeln", "Batch (CSV)"])

# -----------------------
# Tab: Einzel-QR
# -----------------------
with tab_single:
    st.subheader("Einzel-QR")
    data = st.text_area("Inhalt (URL, Text, vCard, WLAN-String …)", placeholder="https://example.org", height=100)

    col1, col2 = st.columns(2)
    with col1:
        logo_file = st.file_uploader("Optional: Logo (PNG, transparent empfohlen)", type=["png"], accept_multiple_files=False)
        logo_scale = st.slider("Logo-Größe", 5, 35, 20, help="in % der kleineren Bildkante")
    with col2:
        use_clear_zone = st.checkbox("Freie Zone um Logo (Clear Zone)")
        clear_zone_margin = st.slider("Breite der Clear Zone", 0, 30, 10, help="in % der Logo-Kante (zusätzlich)")

    if st.button("QR-Code erzeugen", type="primary", disabled=not data):
        try:
            qr = segno.make(data, error=ecc, micro=micro)
        except Exception as e:
            st.error(f"Fehler beim Erzeugen: {e}")
        else:
            if fmt == "SVG":
                # SVG: Logo-Einbettung nicht vorgesehen (rasterisiere nur Vorschau)
                buf = io.BytesIO()
                qr.save(buf, kind="svg", scale=scale, border=border, dark=dark, light=light)
                svg_bytes = buf.getvalue()
                st.success("SVG erstellt.")
                st.download_button("⬇️ SVG herunterladen", data=svg_bytes, file_name="qrcode.svg", mime="image/svg+xml")
                st.write("Vorschau (rasterisiert):")
                st.image(qr.to_pil(scale=6, border=2), caption="Vorschau (Export ist SVG)")
            else:
                # PNG-Erzeugung
                out = io.BytesIO()
                qr.save(out, kind="png", scale=scale, border=border, dark=dark, light=light)
                png_bytes = out.getvalue()

                # Logo-Optionen
                if logo_file is not None:
                    if use_clear_zone:
                        png_bytes = embed_logo_with_clear_zone(
                            png_bytes,
                            logo_file.read(),
                            logo_rel_size=logo_scale / 100.0,
                            margin=clear_zone_margin / 100.0
                        )
                    else:
                        png_bytes = embed_logo_overlay(
                            png_bytes,
                            logo_file.read(),
                            logo_rel_size=logo_scale / 100.0
                        )

                st.success("PNG erstellt.")
                st.image(png_bytes, caption="QR-Code", use_container_width=False)
                st.download_button("⬇️ PNG herunterladen", data=png_bytes, file_name="qrcode.png", mime="image/png")

# -----------------------
# Tab: Batch (CSV)
# -----------------------
with tab_batch:
    st.subheader("Batch-Erstellung aus CSV")
    st.caption("CSV mit Spalte **data** (Pflicht) und optional **filename**. Trennzeichen: Komma oder Semikolon.")
    csv_file = st.file_uploader("CSV hochladen", type=["csv"])
    colb1, colb2 = st.columns(2)
    with colb1:
        allow_logo = st.checkbox("Logo bei PNG im Batch einbetten")
        batch_logo_scale = st.slider("Logo-Größe (Batch)", 5, 35, 20)
    with colb2:
        batch_clear_zone = st.checkbox("Freie Zone um Logo (Batch)")
        batch_clear_zone_margin = st.slider("Clear Zone (Batch)", 0, 30, 10)

    batch_logo = None
    if allow_logo:
        batch_logo = st.file_uploader("Batch-Logo (PNG)", type=["png"], key="batchlogo")

    if csv_file is not None:
        import pandas as pd
        try:
            raw = csv_file.read().decode("utf-8")
            sep = ";" if raw.count(";") > raw.count(",") else ","
            df = pd.read_csv(io.StringIO(raw), sep=sep)

            if "data" not in df.columns:
                st.error("CSV benötigt mindestens eine Spalte namens 'data'.")
            else:
                st.dataframe(df.head())
                if st.button("Batch-QR-Codes generieren", type="primary"):
                    zips = io.BytesIO()
                    import zipfile
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
                                                margin=batch_clear_zone_margin / 100.0
                                            )
                                        else:
                                            png_bytes = embed_logo_overlay(
                                                png_bytes,
                                                logo_bytes,
                                                logo_rel_size=batch_logo_scale / 100.0
                                            )
                                        # Logo-Stream zurückspulen für nächsten Durchlauf
                                        batch_logo.seek(0)
                                    zipf.writestr(f"{name}.png", png_bytes)
                            except Exception as e:
                                zipf.writestr(f"ERROR_row_{idx+1}.txt", f"Fehler für '{name}': {e}")
                    zips.seek(0)
                    st.download_button("⬇️ ZIP herunterladen", data=zips, file_name="qr_batch.zip", mime="application/zip")
        except Exception as e:
            st.error(f"CSV konnte nicht verarbeitet werden: {e}")

st.markdown("---")
st.caption(
    "Hinweis: Für Logos **ECC Q/H** wählen und Logo-Größe moderat halten (10–25%). "
    "Die **Clear Zone** erzeugt einen weißen Bereich um das Logo, der das Scannen erleichtert."
)
