import streamlit as st
import fitz  # PyMuPDF
from PIL import Image
import subprocess
import tempfile
import os
import zipfile
import io

st.set_page_config(page_title="Designer PDF Converter", page_icon="🎨", layout="centered")

st.title("🎨 Designer PDF Converter")
st.write("PDF ফাইল থেকে সরাসরি নির্দিষ্ট DPI ও সাইজের **JPEG, Vector EPS এবং Photoshop PSD** ফাইলে কনভার্ট করুন।")

uploaded_file = st.file_uploader("আপনার PDF ফাইল আপলোড করুন", type=["pdf"])

col1, col2 = st.columns(2)
with col1:
    out_format = st.selectbox("আউটপুট ফরম্যাট সিলেক্ট করুন", ["JPEG", "EPS (Vector)", "PSD (Photoshop)"])
with col2:
    dpi = st.number_input("DPI নির্ধারণ করুন (Print: 300, Web: 72)", min_value=72, max_value=1200, value=300, step=50)

st.subheader("কাস্টম সাইজ - Pixel (ঐচ্ছিক)")
st.caption("খালি রাখলে বা 0 থাকলে অরিজিনাল ডিজাইনের রেশিও অনুযায়ী অটোমেটিক সাইজ হবে।")
col3, col4 = st.columns(2)
with col3:
    custom_w = st.number_input("Width (px)", min_value=0, value=0, step=100)
with col4:
    custom_h = st.number_input("Height (px)", min_value=0, value=0, step=100)

if uploaded_file is not None:
    if st.button("🚀 Convert Now", use_container_width=True):
        with st.spinner("কনভার্ট হচ্ছে... অনুগ্রহ করে অপেক্ষা করুন..."):
            with tempfile.TemporaryDirectory() as tmpdir:
                pdf_path = os.path.join(tmpdir, "input.pdf")
                with open(pdf_path, "wb") as f:
                    f.write(uploaded_file.read())
                
                doc = fitz.open(pdf_path)
                base_name = os.path.splitext(uploaded_file.name)[0]
                output_files = []

                for i in range(len(doc)):
                    page_num = i + 1
                    
                    if out_format == "EPS (Vector)":
                        eps_out = os.path.join(tmpdir, f"{base_name}_page_{page_num}.eps")
                        subprocess.run(["pdftops", "-f", str(page_num), "-l", str(page_num), "-eps", pdf_path, eps_out], check=True)
                        output_files.append(eps_out)
                    
                    else:
                        page = doc.load_page(i)
                        zoom = dpi / 72.0
                        mat = fitz.Matrix(zoom, zoom)
                        pix = page.get_pixmap(matrix=mat, alpha=False)
                        img = Image.frombytes("RGB", [pix.width, pix.height], pix.samples)

                        if custom_w > 0 and custom_h > 0:
                            img = img.resize((custom_w, custom_h), Image.Resampling.LANCZOS)

                        if out_format == "JPEG":
                            jpg_out = os.path.join(tmpdir, f"{base_name}_page_{page_num}.jpg")
                            img.save(jpg_out, "JPEG", dpi=(dpi, dpi), quality=100, subsampling=0)
                            output_files.append(jpg_out)
                        
                        elif out_format == "PSD (Photoshop)":
                            temp_tiff = os.path.join(tmpdir, f"temp_{page_num}.tiff")
                            psd_out = os.path.join(tmpdir, f"{base_name}_page_{page_num}.psd")
                            img.save(temp_tiff, "TIFF", dpi=(dpi, dpi))
                            subprocess.run(["convert", temp_tiff, "-density", str(dpi), psd_out], check=True)
                            output_files.append(psd_out)

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
                    st.success(f"✅ মোট {len(output_files)}টি পেজ সফলভাবে কনভার্ট হয়েছে!")
                    st.download_button(
                        label="⬇️ Download All Files (ZIP)",
                        data=zip_buffer.getvalue(),
                        file_name=f"{base_name}_converted.zip",
                        mime="application/zip",
                        use_container_width=True
                    )
