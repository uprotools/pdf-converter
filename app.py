import streamlit as st
import fitz  # PyMuPDF
from PIL import Image
import pytesseract
import subprocess
import tempfile
import os
import zipfile
import io
import xml.etree.ElementTree as ET

st.set_page_config(page_title="Smart Text & Vector PDF Converter", page_icon="🎨", layout="centered")

st.title("🎨 Smart PDF to Editable Vector, PSD & JPEG")
st.write("**Live Text Detection, OCR** এবং **Vector Layer Separation** সহ প্রফেশনাল কনভার্টার।")

uploaded_file = st.file_uploader("আপনার PDF ফাইল আপলোড করুন", type=["pdf"])

if uploaded_file is not None:
    pdf_bytes = uploaded_file.read()
    doc_check = fitz.open(stream=pdf_bytes, filetype="pdf")
    
    # --- TEXT DETECTION DIAGNOSTIC ---
    total_live_chars = 0
    detected_fonts = set()
    for page in doc_check:
        text_Page = page.get_text("text").strip()
        total_live_chars += len(text_Page)
        for f in page.get_fonts():
            detected_fonts.add(f[3])

    st.subheader("🔍 PDF Text & Layer Analysis (ফাইল রিপোর্ট)")
    if total_live_chars > 0:
        st.success(f"✅ **Live Editable Text Detected!** এই PDF-এ মোট **{total_live_chars}** টি ক্যারেক্টার এবং **{len(detected_fonts)}** টি ফন্ট পাওয়া গেছে।")
        if detected_fonts:
            st.caption(f"**ব্যবহৃত ফন্টসমূহ:** {', '.join(list(detected_fonts)[:8])}")
        st.warning("⚠️ **জরুরি নোট:** সাধারণ `.eps` ইঞ্জিন ফন্ট মিসিং থাকলে টেক্সটকে ভেঙে ছবি/শেপ বানিয়ে ফেলে। তাই Illustrator-এ **১০০% এডিটেবল টেক্সট এবং আলাদা লেয়ার** পেতে নিচের ১ নম্বর অপশনটি (**Illustrator Editable Package**) সিলেক্ট করুন।")
    else:
        st.error("❌ **কোনো Live Text পাওয়া যায়নি!** আপনার PDF ফাইলটি মূলত একটি **Flat Image (ছবি)** অথবা এর টেক্সটগুলো আগে থেকেই **Outlined (Curve)** করা।")
        st.info("💡 যেহেতু ফাইলে আসল টেক্সট নেই, তাই নিচে **OCR Engine** চালু করা হয়েছে যা ছবি স্ক্যান করে টেক্সটগুলো আলাদা করে দেবে।")

    col1, col2 = st.columns(2)
    with col1:
        out_format = st.selectbox(
            "আউটপুট ফরম্যাট সিলেক্ট করুন",
            [
                "1. Illustrator Editable Package (Live Text SVG + EPS + Extracted Text)",
                "2. Direct EPS (Poppler/Inkscape Vector)",
                "3. PSD + OCR Text & Separated Image Layers (ZIP)",
                "4. High-DPI JPEG"
            ]
        )
    with col2:
        dpi = st.number_input("DPI নির্ধারণ করুন (Print: 300, Web: 72)", min_value=72, max_value=1200, value=300, step=50)

    col3, col4 = st.columns(2)
    with col3:
        custom_w = st.number_input("Custom Width - px (ঐচ্ছিক)", min_value=0, value=0, step=100)
    with col4:
        custom_h = st.number_input("Custom Height - px (ঐচ্ছিক)", min_value=0, value=0, step=100)

    if st.button("🚀 Convert & Extract Text/Layers", use_container_width=True):
        with st.spinner("টেক্সট ডিটেকশন এবং লেয়ার প্রসেস হচ্ছে..."):
            with tempfile.TemporaryDirectory() as tmpdir:
                pdf_path = os.path.join(tmpdir, "input.pdf")
                with open(pdf_path, "wb") as f:
                    f.write(pdf_bytes)
                
                doc = fitz.open(pdf_path)
                base_name = os.path.splitext(uploaded_file.name)[0]
                output_files = []

                for i in range(len(doc)):
                    page_num = i + 1
                    page = doc.load_page(i)
                    zoom = dpi / 72.0
                    mat = fitz.Matrix(zoom, zoom)

                    # --- TEXT EXTRACTION (LIVE OR OCR) ---
                    extracted_text_path = os.path.join(tmpdir, f"Page_{page_num}_Detected_Text.txt")
                    live_text_dict = page.get_text("dict")
                    has_page_text = False
                    
                    with open(extracted_text_path, "w", encoding="utf-8") as tf:
                        tf.write(f"=== PAGE {page_num} DETECTED TEXT & FONT INFO ===\n\n")
                        for b in live_text_dict["blocks"]:
                            if b["type"] == 0:
                                for line in b["lines"]:
                                    for span in line["spans"]:
                                        t = span["text"].strip()
                                        if t:
                                            has_page_text = True
                                            tf.write(f"Text: {t}  |  Font: {span['font']}  |  Size: {round(span['size'], 1)}pt\n")
                        
                        # যদি লাইভ টেক্সট না থাকে, তবে OCR দিয়ে ছবি থেকে টেক্সট ডিটেক্ট করা হবে
                        if not has_page_text:
                            tf.write("[No Live Vector Text Found - Running OCR Image Text Detection...]\n\n")
                            pix_ocr = page.get_pixmap(matrix=fitz.Matrix(300/72, 300/72), alpha=False)
                            img_ocr = Image.frombytes("RGB", [pix_ocr.width, pix_ocr.height], pix_ocr.samples)
                            try:
                                ocr_result = pytesseract.image_to_string(img_ocr, lang="eng+ben")
                                tf.write(ocr_result if ocr_result.strip() else "কোনো টেক্সট খুঁজে পাওয়া যায়নি।")
                            except Exception as e:
                                tf.write(f"OCR Error: {str(e)}")

                    # OPTION 1: Illustrator Editable Package
                    if out_format.startswith("1."):
                        output_files.append(extracted_text_path)
                        
                        # A. Live Text SVG (Illustrator opens this with 100% editable Font Text & Layers)
                        svg_live_path = os.path.join(tmpdir, f"{base_name}_page_{page_num}_OPEN_IN_ILLUSTRATOR_FOR_LIVE_TEXT.svg")
                        svg_raw = page.get_svg_image(text_as_path=False)
                        
                        # যদি ফাইলটি স্ক্যান করা ছবি হয়, তবে OCR দিয়ে সরাসরি এডিটেবল SVG টেক্সট লেয়ার তৈরি করা
                        if not has_page_text:
                            pix_bg = page.get_pixmap(matrix=mat, alpha=False)
                            img_bg = Image.frombytes("RGB", [pix_bg.width, pix_bg.height], pix_bg.samples)
                            ocr_data = pytesseract.image_to_data(img_bg, output_type=pytesseract.Output.DICT)
                            
                            svg_lines = [f'<svg xmlns="http://www.w3.org/2000/svg" width="{pix_bg.width}" height="{pix_bg.height}">']
                            svg_lines.append('<g id="OCR_Editable_Text_Layer">')
                            for idx in range(len(ocr_data["text"])):
                                word = ocr_data["text"][idx].strip()
                                if word and int(ocr_data["conf"][idx]) > 40:
                                    x, y, h = ocr_data["left"][idx], ocr_data["top"][idx], ocr_data["height"][idx]
                                    svg_lines.append(f'<text x="{x}" y="{y + h}" font-family="Arial" font-size="{h}px" fill="#000000">{word}</text>')
                            svg_lines.append('</g></svg>')
                            with open(svg_live_path, "w", encoding="utf-8") as sf:
                                sf.write("\n".join(svg_lines))
                        else:
                            with open(svg_live_path, "w", encoding="utf-8") as sf:
                                sf.write(svg_raw)
                        output_files.append(svg_live_path)

                        # B. Standard EPS (via Inkscape Level 3)
                        eps_out = os.path.join(tmpdir, f"{base_name}_page_{page_num}_Vector.eps")
                        subprocess.run([
                            "pdftops", "-f", str(page_num), "-l", str(page_num),
                            "-eps", "-level3", pdf_path, eps_out
                        ], check=True)
                        output_files.append(eps_out)

                    # OPTION 2: Direct EPS
                    elif out_format.startswith("2."):
                        eps_out = os.path.join(tmpdir, f"{base_name}_page_{page_num}.eps")
                        subprocess.run([
                            "pdftops", "-f", str(page_num), "-l", str(page_num),
                            "-eps", "-level3", pdf_path, eps_out
                        ], check=True)
                        output_files.append(eps_out)

                    # OPTION 3: PSD + Separated Layers + OCR Text
                    elif out_format.startswith("3."):
                        output_files.append(extracted_text_path)
                        
                        # Extract all embedded raster images separately
                        for img_idx, img_info in enumerate(page.get_images(full=True)):
                            base_img = doc.extract_image(img_info[0])
                            img_path = os.path.join(tmpdir, f"Page_{page_num}_Separated_Layer_{img_idx+1}.{base_img['ext']}")
                            with open(img_path, "wb") as imf:
                                imf.write(base_img["image"])
                            output_files.append(img_path)

                        # High-Res PSD
                        pix = page.get_pixmap(matrix=mat, alpha=True)
                        img = Image.frombytes("RGBA", [pix.width, pix.height], pix.samples)
                        if custom_w > 0 and custom_h > 0:
                            img = img.resize((custom_w, custom_h), Image.Resampling.LANCZOS)
                        temp_png = os.path.join(tmpdir, f"temp_{page_num}.png")
                        psd_out = os.path.join(tmpdir, f"{base_name}_page_{page_num}.psd")
                        img.save(temp_png, "PNG", dpi=(dpi, dpi))
                        subprocess.run(["convert", temp_png, "-density", str(dpi), psd_out], check=True)
                        output_files.append(psd_out)

                    # OPTION 4: High-DPI JPEG
                    elif out_format.startswith("4."):
                        pix = page.get_pixmap(matrix=mat, alpha=False)
                        img = Image.frombytes("RGB", [pix.width, pix.height], pix.samples)
                        if custom_w > 0 and custom_h > 0:
                            img = img.resize((custom_w, custom_h), Image.Resampling.LANCZOS)
                        jpg_out = os.path.join(tmpdir, f"{base_name}_page_{page_num}.jpg")
                        img.save(jpg_out, "JPEG", dpi=(dpi, dpi), quality=100, subsampling=0)
                        output_files.append(jpg_out)

                doc.close()

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
                    st.success(f"✅ টেক্সট এবং লেয়ারসহ মোট {len(output_files)}টি ফাইল তৈরি হয়েছে!")
                    st.download_button(
                        label="⬇️ Download Editable Package (ZIP)",
                        data=zip_buffer.getvalue(),
                        file_name=f"{base_name}_Editable_Package.zip",
                        mime="application/zip",
                        use_container_width=True
                    )
