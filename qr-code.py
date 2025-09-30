import io
import os
import streamlit as st
import segno

# Optionales PIL-Import erst, wenn Logo benutzt wird
def embed_logo_png(png_bytes: bytes, logo_bytes: bytes, logo_rel_size: float = 0.20) -> bytes:
    try:
        from PIL import Image
    except Exception:
        st.warning("Pillow ist nicht installiert – Logo wird ignoriert.")
        return png_bytes

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

st.set_page_config(page_title="QR-Code Generator", page_icon="🔳", layout="centered")

st.title("🔳 QR-Code Generator")
st.write("Erzeuge QR-Codes als **PNG** oder **SVG** – inkl. Farbe, Fehlerkorrektur, Rand, Größe und optionalem Logo.")

with st.sidebar:
    st.header("⚙️ Einstellungen")
    ecc = st.selectbox("Fehlerkorrektur", options=["L", "M", "Q", "H"], index=1, help="Höher = robuster")
    scale = st.slider("Skalierung (PNG/SVG)", 2, 20, 8)
    border = st.slider("Rand / Quiet Zone", 0, 10, 4)
    dark = st.color_picker("Dunkel (Module)", "#000000")
    light = st.color_picker("Hell (Hintergrund)", "#FFFFFF")
    fmt = st.radio("Format", ["PNG", "SVG"], horizontal=True)
    micro = st.checkbox("Micro-QR versuchen (nur sehr kurze Daten)")

    st.caption("💡 Tipp: Für SVG kann der Hintergrund später transparent gesetzt werden – per Vektorbearbeitung.")

tab_single, tab_batch = st.tabs(["Einzeln", "Batch (CSV)"])

with tab_single:
    st.subheader("Einzel-QR")
    data = st.text_area("Inhalt (URL, Text, vCard, WLAN-String …)", placeholder="https://example.org", height=100)
    col1, col2 = st.columns(2)
    with col1:
        logo_file = st.file_uploader("Optional: Logo (PNG, transparent empfohlen)", type=["png"], accept_multiple_files=False)
    with col2:
        logo_scale = st.slider("Logo-Größe (relativ)", 5, 35, 20, help="in % der kleineren Bildkante")

    if st.button("QR-Code erzeugen", type="primary", disabled=not data):
        try:
            qr = segno.make(data, error=ecc, micro=micro)
        except Exception as e:
            st.error(f"Fehler beim Erzeugen: {e}")
        else:
            if fmt == "SVG":
                # Hinweis: Logo-Einbettung ist hier nicht vorgesehen
                buf = io.BytesIO()
                qr.save(
                    buf,
                    kind="svg",
                    scale=scale,
                    border=border,
                    dark=dark,
                    light=light
                )
                svg_bytes = buf.getvalue()
                st.success("SVG erstellt.")
                st.download_button("⬇️ SVG herunterladen", data=svg_bytes, file_name="qrcode.svg", mime="image/svg+xml")
                st.write("Vorschau:")
                st.image(qr.to_pil(scale=6, border=2), caption="Rasterisierte Vorschau (Export ist SVG)")
            else:
                buf = io.BytesIO()
                qr.save(
                    buf,
                    kind="png",
                    scale=scale,
                    border=border,
                    dark=dark,
                    light=light
                )
                png_bytes = buf.getvalue()
                if logo_file is not None:
                    png_bytes = embed_logo_png(png_bytes, logo_file.read(), logo_rel_size=logo_scale/100.0)

                st.success("PNG erstellt.")
                st.image(png_bytes, caption="QR-Code", use_container_width=False)
                st.download_button("⬇️ PNG herunterladen", data=png_bytes, file_name="qrcode.png", mime="image/png")

with tab_batch:
    st.subheader("Batch-Erstellung aus CSV")
    st.caption("CSV mit Spalte **data** (Pflicht) und optional **filename**. Trennzeichen: Komma oder Semikolon.")
    csv_file = st.file_uploader("CSV hochladen", type=["csv"])
    allow_logo = st.checkbox("Logo bei PNG auch im Batch einbetten")
    batch_logo = None
    batch_logo_scale = logo_scale
    if allow_logo:
        batch_logo = st.file_uploader("Batch-Logo (PNG)", type=["png"], key="batchlogo")

    if csv_file is not None:
        import pandas as pd
        try:
            # Versuche ; oder , automatisch
            content = csv_file.read().decode("utf-8")
            sep = ";" if content.count(";") > content.count(",") else ","
            df = pd.read_csv(io.StringIO(content), sep=sep)
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
                            name = str(row["filename"]) if "filename" in df.columns and not pd.isna(row["filename"]) else f"qr_{idx+1}"
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
                                        png_bytes = embed_logo_png(png_bytes, batch_logo.read(), logo_rel_size=batch_logo_scale/100.0)
                                        # logo Bytes erneut bereitstellen
                                        batch_logo.seek(0)
                                    zipf.writestr(f"{name}.png", png_bytes)
                            except Exception as e:
                                zipf.writestr(f"ERROR_row_{idx+1}.txt", f"Fehler für '{name}': {e}")
                    zips.seek(0)
                    st.download_button("⬇️ ZIP herunterladen", data=zips, file_name="qr_batch.zip", mime="application/zip")
        except Exception as e:
            st.error(f"CSV konnte nicht verarbeitet werden: {e}")

st.markdown("---")
st.caption("Hinweis: Hoher Kontrast (dunkel auf hell) und ausreichend Rand (≥4) verbessern die Scan-Qualität. "
           "Für Logos empfiehlt sich ECC **Q/H** und ein Logo-Anteil von 10–25%.")
