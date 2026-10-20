import streamlit as st
import fitz  # PyMuPDF
from PIL import Image
import subprocess
import tempfile
import os
import zipfile
import io
import shutil

st.set_page_config(page_title="Inkscape & Cairo EPS Converter", page_icon="🎨", layout="centered")

st.title("🎨 Pro PDF to EPS / PSD / JPEG Converter")
st.write("**Inkscape** এবং **Cairo Vector Engine** ব্যবহার করে ১০০% ভেক্টর কোয়ালিটি, লেয়ার ও টেক্সটসহ কনভার্ট করুন।")

# সার্ভার স্ট্যাটাস চেক (Inkscape ও Cairo ইনস্টল হয়েছে কিনা তা দেখাবে)
inkscape_ready = shutil.which("inkscape") is not None
cairo_ready = shutil.which("pdftocairo") is not None

with st.expander("⚙️ Active Vector Engines Status (সার্ভার ইঞ্জিন স্ট্যাটাস)", expanded=False):
    st.write(f"✅ **Inkscape Vector Engine:** {'Active' if inkscape_ready else 'Not Found (Reboot App)'}")
    st.write(f"✅ **Cairo Vector Engine (pdftocairo):** {'Active' if cairo_ready else 'Not Found (Reboot App)'}")

uploaded_file = st.file_uploader("আপনার PDF ফাইল আপলোড করুন", type=["pdf"])

col1, col2 = st.columns(2)
with col1:
    out_format = st.selectbox(
        "আউটপুট ফরম্যাট ও ইঞ্জিন সিলেক্ট করুন",
        [
            "EPS - Inkscape + Cairo Hybrid (Editable Text & Layers)",
            "EPS - Pure Cairo Engine (PostScript Level 3 Vector)",
            "EPS - Inkscape Outlined (Curve Shapes - No Font Issue)",
            "JPEG (High Resolution)",
            "PSD (Photoshop + Layer Assets)"
        ]
    )
with col2:
    dpi = st.number_input("DPI নির্ধারণ করুন (Print: 300, Web: 72)", min_value=72, max_value=1200, value=300, step=50)

st.subheader("কাস্টম সাইজ - Pixel (শুধুমাত্র JPEG/PSD এর জন্য)")
col3, col4 = st.columns(2)
with col3:
    custom_w = st.number_input("Width (px)", min_value=0, value=0, step=100)
with col4:
    custom_h = st.number_input("Height (px)", min_value=0, value=0, step=100)

if uploaded_file is not None:
    if st.button("🚀 Convert Now", use_container_width=True):
        with st.spinner("Inkscape এবং Cairo ইঞ্জিন দিয়ে ভেক্টর প্রসেস হচ্ছে..."):
            with tempfile.TemporaryDirectory() as tmpdir:
                pdf_path = os.path.join(tmpdir, "input.pdf")
                with open(pdf_path, "wb") as f:
                    f.write(uploaded_file.read())
                
                doc = fitz.open(pdf_path)
                base_name = os.path.splitext(uploaded_file.name)[0]
                output_files = []

                for i in range(len(doc)):
                    page_num = i + 1
                    page = doc.load_page(i)
                    zoom = dpi / 72.0
                    mat = fitz.Matrix(zoom, zoom)

                    # ১. Inkscape + Cairo Hybrid (Editable Live Text & Vector Groups)
                    if out_format == "EPS - Inkscape + Cairo Hybrid (Editable Text & Layers)":
                        temp_svg = os.path.join(tmpdir, f"temp_{page_num}.svg")
                        eps_out = os.path.join(tmpdir, f"{base_name}_page_{page_num}_Editable.eps")
                        
                        # টেক্সটকে লাইভ ফন্ট রেখে SVG জেনারেট করা
                        svg_content = page.get_svg_image(text_as_path=False)
                        with open(temp_svg, "w", encoding="utf-8") as sf:
                            sf.write(svg_content)
                        
                        # Inkscape CLI দিয়ে সরাসরি EPS-এ রূপান্তর (ব্যর্থ হলে Cairo ব্যাকআপ)
                        try:
                            subprocess.run([
                                "inkscape", temp_svg,
                                f"--export-filename={eps_out}",
                                "--export-ps-level=3"
                            ], check=True)
                        except Exception:
                            subprocess.run([
                                "pdftocairo", "-eps", "-level3",
                                "-f", str(page_num), "-l", str(page_num),
                                pdf_path, eps_out
                            ], check=True)
                        output_files.append(eps_out)

                    # ২. Pure Cairo Engine (Direct PDF to EPS via Cairo Graphics)
                    elif out_format == "EPS - Pure Cairo Engine (PostScript Level 3 Vector)":
                        eps_out = os.path.join(tmpdir, f"{base_name}_page_{page_num}_Cairo.eps")
                        subprocess.run([
                            "pdftocairo", "-eps", "-level3",
                            "-f", str(page_num), "-l", str(page_num),
                            pdf_path, eps_out
                        ], check=True)
                        output_files.append(eps_out)

                    # ৩. Inkscape Outlined Vector (ফন্ট মিসিং সমস্যা এড়াতে সব টেক্সট ভেক্টর শেপ হয়ে যাবে)
                    elif out_format == "EPS - Inkscape Outlined (Curve Shapes - No Font Issue)":
                        temp_svg = os.path.join(tmpdir, f"temp_{page_num}.svg")
                        eps_out = os.path.join(tmpdir, f"{base_name}_page_{page_num}_Outlined.eps")
                        
                        svg_content = page.get_svg_image(text_as_path=True)
                        with open(temp_svg, "w", encoding="utf-8") as sf:
                            sf.write(svg_content)
                            
                        try:
                            subprocess.run([
                                "inkscape", temp_svg,
                                f"--export-filename={eps_out}",
                                "--export-text-to-path",
                                "--export-ps-level=3"
                            ], check=True)
                        except Exception:
                            subprocess.run([
                                "pdftocairo", "-eps", "-level3",
                                "-f", str(page_num), "-l", str(page_num),
                                pdf_path, eps_out
                            ], check=True)
                        output_files.append(eps_out)

                    # ৪. High-DPI JPEG
                    elif "JPEG" in out_format:
                        pix = page.get_pixmap(matrix=mat, alpha=False)
                        img = Image.frombytes("RGB", [pix.width, pix.height], pix.samples)
                        if custom_w > 0 and custom_h > 0:
                            img = img.resize((custom_w, custom_h), Image.Resampling.LANCZOS)
                        jpg_out = os.path.join(tmpdir, f"{base_name}_page_{page_num}.jpg")
                        img.save(jpg_out, "JPEG", dpi=(dpi, dpi), quality=100, subsampling=0)
                        output_files.append(jpg_out)

                    # ৫. PSD + Separated Layers
                    elif "PSD" in out_format:
                        # A. Editable Vector SVG Layer
                        svg_layer = os.path.join(tmpdir, f"{base_name}_page_{page_num}_Vector_Layers.svg")
                        with open(svg_layer, "w", encoding="utf-8") as sf:
                            sf.write(page.get_svg_image(text_as_path=False))
                        output_files.append(svg_layer)

                        # B. Individual Embedded Images
                        for img_idx, img_info in enumerate(page.get_images(full=True)):
                            base_img = doc.extract_image(img_info[0])
                            img_path = os.path.join(tmpdir, f"Page_{page_num}_Asset_{img_idx+1}.{base_img['ext']}")
                            with open(img_path, "wb") as imf:
                                imf.write(base_img["image"])
                            output_files.append(img_path)

                        # C. Master High-Res PSD
                        pix = page.get_pixmap(matrix=mat, alpha=True)
                        img = Image.frombytes("RGBA", [pix.width, pix.height], pix.samples)
                        if custom_w > 0 and custom_h > 0:
                            img = img.resize((custom_w, custom_h), Image.Resampling.LANCZOS)
                        temp_png = os.path.join(tmpdir, f"temp_{page_num}.png")
                        psd_out = os.path.join(tmpdir, f"{base_name}_page_{page_num}.psd")
                        img.save(temp_png, "PNG", dpi=(dpi, dpi))
                        subprocess.run(["convert", temp_png, "-density", str(dpi), psd_out], check=True)
                        output_files.append(psd_out)

                doc.close()

                # ডাউনলোড বাটন
                if len(output_files) == 1:
                    with open(output_files[0], "rb") as f:
                        file_data = f.read()
                    file_ext = os.path.splitext(output_files[0])[1]
                    st.success("✅ সফলভাবে কনভার্ট হয়েছে!")
                    st.download_button(
                        label=f"⬇️ Download {file_ext.upper()} File",
                        data=file_data,
                        file_name=os.path.basename(output_files[0]),
                        mime="application/octet-stream",
                        use_container_width=True
                    )
                else:
                    zip_buffer = io.BytesIO()
                    with zipfile.ZipFile(zip_buffer, "w", zipfile.ZIP_DEFLATED) as zf:
                        for file_path in output_files:
                            zf.write(file_path, os.path.basename(file_path))
                    st.success(f"✅ মোট {len(output_files)}টি ফাইল তৈরি হয়েছে!")
                    st.download_button(
                        label="⬇️ Download All Files (ZIP)",
                        data=zip_buffer.getvalue(),
                        file_name=f"{base_name}_converted_files.zip",
                        mime="application/zip",
                        use_container_width=True
                    )
