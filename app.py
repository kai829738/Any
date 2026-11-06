import os
import shutil
import subprocess
import tempfile

import gdown
import gradio as gr
import pymupdf
from PIL import Image
from pdf2docx import Converter

# Streamlined Categories for Free Tier Performance
CATEGORY_MAP = {
    "Images": ["png", "jpg", "jpeg", "webp", "bmp", "tiff", "tif", "gif", "ico"],
    "Audio": ["mp3", "wav", "aac", "flac", "ogg", "m4a", "wma", "opus"],
    "Documents": ["pdf", "docx", "doc", "rtf", "odt", "txt"]
}

# Streamlined Target Options (Restored Document Formats)
FORMAT_OPTIONS = {
    "Images": ["png", "jpg", "jpeg", "webp", "bmp", "tiff", "tif", "gif", "ico"],
    "Audio": ["mp3", "wav", "aac", "flac", "ogg", "m4a", "wma", "opus"],
    "Documents": ["pdf", "docx", "doc", "txt", "rtf", "odt"] 
}

css = """
body, .gradio-container {
    background-color: #121316 !important;
    color: #e2e2e2 !important;
    font-family: 'Inter', sans-serif !important;
}
.main-box {
    background-color: #1a1b1e;
    border-radius: 12px;
    padding: 2rem;
    max-width: 850px;
    margin: 0 auto;
    border: 1px solid #2e3035;
}
.convert-btn {
    background-color: #dc3545 !important;
    color: white !important;
    border: none !important;
    font-weight: bold !important;
    padding: 12px 24px !important;
    font-size: 15px !important;
}
.convert-btn:hover {
    background-color: #bb2d3b !important;
}
.download-btn {
    background-color: #198754 !important;
    color: white !important;
    border: none !important;
    font-weight: bold !important;
    padding: 12px 24px !important;
    font-size: 15px !important;
}
.download-btn:hover {
    background-color: #157347 !important;
}
.badge-container {
    display: flex;
    flex-wrap: wrap;
    gap: 8px;
    margin-top: 15px;
}
.badge {
    background-color: #25262b;
    padding: 5px 10px;
    border-radius: 6px;
    font-size: 11px;
    font-weight: bold;
    color: #adb5bd;
    border: 1px solid #343a40;
}
"""

def get_file_path(file_obj):
    if isinstance(file_obj, str):
        return file_obj
    if hasattr(file_obj, "name"):
        return file_obj.name
    if isinstance(file_obj, dict) and "path" in file_obj:
        return file_obj["path"]
    return str(file_obj)

def detect_file_info(uploaded_files):
    if not uploaded_files:
        return (
            gr.update(value="Images"),
            gr.update(choices=FORMAT_OPTIONS["Images"], value="jpg"),
            "ℹ️ Upload a file to trigger auto-detection.",
        )

    first_file = uploaded_files[0]
    filename = os.path.basename(get_file_path(first_file))
    ext = filename.rsplit(".", 1)[-1].lower() if "." in filename else ""

    detected_category = "Images" # Default
    for category, extensions in CATEGORY_MAP.items():
        if ext in extensions:
            detected_category = category
            break

    choices = FORMAT_OPTIONS.get(detected_category, CATEGORY_MAP.get(detected_category, ["jpg"]))
    if ext in choices:
        choices = [choice for choice in choices if choice != ext]

    default_target = choices[0] if choices else ""
    status_msg = (
        f"⚡ **Detected**: `{filename}` (Type: **{ext.upper()}**) "
        f"➔ Set to **{detected_category}** converter."
    )
    return gr.update(value=detected_category), gr.update(choices=choices, value=default_target), status_msg

def update_choices_for_category(category):
    choices = FORMAT_OPTIONS.get(category, CATEGORY_MAP.get(category, ["jpg"]))
    return gr.update(choices=choices, value=choices[0] if choices else "")

def process_file(local_files, drive_id, category, output_ext):
    input_paths = []
    status_log = ""
    is_temp_download = False

    if local_files:
        input_paths = [get_file_path(file_obj) for file_obj in local_files]
        status_log += f"📥 Using {len(input_paths)} local file(s)...\n"

    if drive_id:
        status_log += "📥 Downloading from Google Drive...\n"
        try:
            drive_path = gdown.download(id=drive_id, quiet=False)
            if drive_path and os.path.exists(drive_path):
                input_paths.append(drive_path)
                is_temp_download = True
            else:
                return "❌ Download failed. Check ID and sharing permissions.", gr.update(visible=False)
        except Exception as exc:
            return f"❌ Download error: {exc}", gr.update(visible=False)

    if not input_paths:
        return "⚠️ Please upload a file or supply a Google Drive ID.", gr.update(visible=False)

    if not output_ext:
        return "⚠️ Please select a target output format.", gr.update(visible=False)

    output_ext = output_ext.strip().replace(".", "").lower()
    input_path = input_paths[0]
    input_ext = input_path.rsplit(".", 1)[-1].lower() if "." in input_path else ""
    base_name = os.path.splitext(os.path.basename(input_path))[0]

    final_filename = f"{base_name}_converted.{output_ext}"
    status_log += f"⏳ Running {category} conversion ({input_ext.upper()} ➔ {output_ext.upper()})...\n"

    try:
        # 1. AUDIO (Fast & Lightweight)
        if category == "Audio":
            command = ["ffmpeg", "-i", input_path, "-vn", final_filename, "-y", "-loglevel", "error"]
            subprocess.run(command, check=True)
            status_log += "✅ Audio converted successfully via FFmpeg.\n"

        # 2. IMAGES (Includes High-Res ICO Fix)
        elif category == "Images":
            image = Image.open(input_path)
            if output_ext in ["jpg", "jpeg"] and image.mode in ("RGBA", "P"):
                image = image.convert("RGB")
            
            if output_ext == "ico":
                image = image.convert("RGBA")
                width, height = image.size
                max_dim = max(width, height)
                square_img = Image.new("RGBA", (max_dim, max_dim), (255, 255, 255, 0))
                square_img.paste(image, ((max_dim - width) // 2, (max_dim - height) // 2))
                square_img.save(final_filename, format="ICO", sizes=[(16, 16), (32, 32), (48, 48), (64, 64), (128, 128), (256, 256)])
            else:
                image.save(final_filename)
            status_log += f"✅ Image converted to {output_ext.upper()} via Pillow.\n"

        # 3. DOCUMENTS (Restored Full Conversion)
        elif category == "Documents":
            if input_ext == "pdf" and output_ext in ["doc", "docx"]:
                cv = Converter(input_path)
                cv.convert(final_filename)
                cv.close()
                status_log += "✅ PDF converted to Word.\n"
            elif input_ext == "pdf" and output_ext == "txt":
                pdf_doc = pymupdf.open(input_path)
                with open(final_filename, "w", encoding="utf-8") as output_file:
                    for page in pdf_doc:
                        output_file.write(page.get_text() + "\n--- PAGE BREAK ---\n")
                pdf_doc.close()
                status_log += "✅ PDF text extracted successfully.\n"
            else:
                out_dir = os.path.abspath(".")
                subprocess.run(
                    ["libreoffice", "--headless", "--convert-to", output_ext, input_path, "--outdir", out_dir],
                    check=True,
                )
                lo_file = os.path.join(out_dir, f"{base_name}.{output_ext}")
                if os.path.exists(lo_file) and lo_file != final_filename:
                    shutil.move(lo_file, final_filename)
                status_log += f"✅ Document converted to {output_ext.upper()}.\n"

    except Exception as exc:
        status_log += f"❌ Conversion Error: {exc}\n"
        return status_log, gr.update(visible=False)
    finally:
        if is_temp_download and "drive_path" in locals() and os.path.exists(drive_path):
            try:
                os.remove(drive_path)
            except OSError:
                pass

    if os.path.exists(final_filename):
        return status_log, gr.update(value=final_filename, visible=True)

    return status_log, gr.update(visible=False)


categories_list = ["Images", "Audio", "Documents"]

with gr.Blocks(css=css) as app:
    gr.HTML(
        """
        <div style="text-align: center; margin: 25px 0 15px 0;">
            <h1 style="color: white; font-weight: bold; font-size: 34px;">Universal Media Converter</h1>
            <p style="color: #adb5bd; font-size: 14px;">Fast, lightweight conversions for Images, Audio, and Documents.</p>
        </div>
        """
    )

    with gr.Column(elem_classes="main-box"):
        local_files = gr.File(label="Upload File(s) (Auto-detects format)", file_count="multiple")
        drive_id = gr.Textbox(label="Or Google Drive File ID", placeholder="Paste Drive ID here if not uploading locally...")
        detect_banner = gr.Markdown("ℹ️ Upload a file to trigger auto-detection.")

        with gr.Row():
            category_dropdown = gr.Dropdown(label="File Category", choices=categories_list, value="Images")
            target_ext = gr.Dropdown(
                label="Target Format",
                choices=FORMAT_OPTIONS["Images"],
                value="jpg",
                allow_custom_value=True,
            )

        convert_btn = gr.Button("Convert File", elem_classes="convert-btn")

        with gr.Row():
            status_output = gr.Textbox(label="Process Log", interactive=False, lines=4)
            download_btn = gr.DownloadButton("⬇️ Download Converted File", elem_classes="download-btn", visible=False)

    badges_markup = ""
    for category in categories_list:
        sub_badges = "".join(
            f'<span class="badge">{ext.upper()}</span>' for ext in CATEGORY_MAP[category][:8]
        )
        badges_markup += (
            f"<div style='margin-top:12px;'><b style='color:#dc3545;'>{category}:</b> "
            f"<div class='badge-container'>{sub_badges}</div></div>"
        )

    gr.HTML(
        f"""
        <div style="max-width: 850px; margin: 30px auto; padding: 10px;">
            <h4 style="color: white; margin-bottom: 5px;">Supported Formats Overview</h4>
            {badges_markup}
        </div>
        """
    )

    local_files.change(
        fn=detect_file_info,
        inputs=[local_files],
        outputs=[category_dropdown, target_ext, detect_banner],
    )
    category_dropdown.change(
        fn=update_choices_for_category,
        inputs=[category_dropdown],
        outputs=[target_ext],
    )
    convert_btn.click(
        fn=process_file,
        inputs=[local_files, drive_id, category_dropdown, target_ext],
        outputs=[status_output, download_btn],
    )

if __name__ == "__main__":
    app.launch(server_name="0.0.0.0", server_port=10000)
