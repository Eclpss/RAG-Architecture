import os
import base64
import requests
import json # Make sure this is at the top of your file!
import fitz  # PyMuPDF
from flask import Flask, request, jsonify

app = Flask(__name__)

@app.route('/test_vision', methods=['POST'])
def test_vision():
    if 'file' not in request.files:
        return jsonify({"status": "error", "message": "No file sent!"}), 400

    pdf_file = request.files['file']
    temp_pdf_path = "./test_temp.pdf"
    pdf_file.save(temp_pdf_path)

    print(f"\n🔥 CAUGHT TEST PDF: {pdf_file.filename} 🔥")
    print("🔨 Checking for digital 'Braille' text with PyMuPDF...")
    
    raw_text = ""
    try:
        with fitz.open(temp_pdf_path) as doc:
            for page in doc:
                raw_text += page.get_text()
    except Exception as e:
        return jsonify({"status": "error", "message": f"PyMuPDF crashed: {e}"}), 500

    # THE MAGIC FALLBACK TRIGGER
    if not raw_text.strip():
        print("🚨 BLANK PDF DETECTED! Engaging Qwen-VL 32B Vision Fallback...")
        raw_text = ""
        
        with fitz.open(temp_pdf_path) as doc:
            for page in doc:
                print(f"📸 Taking picture of page {page.number}...")
                pix = page.get_pixmap(dpi=150) 
                temp_img_path = f"./test_page_{page.number}.png"
                pix.save(temp_img_path)

                with open(temp_img_path, "rb") as img_file:
                    b64_image = base64.b64encode(img_file.read()).decode('utf-8')

                print(f"👁️‍🗨️ Sending Page {page.number} pixels to Qwen-VL...")
                response = requests.post("http://localhost:11434/api/generate", json={
                    "model": "qwen2.5vl:7b", 
                    "prompt": "You are a precise Optical Character Recognition (OCR) engine. Transcribe all text in the image exactly as written. Output ONLY the raw text.",
                    "images": [b64_image],
                    "stream": False
                })

                if response.status_code == 200:
                    extracted = response.json().get("response", "")
                    raw_text += extracted + "\n\n"
                    print("✅ Qwen-VL successfully read the page!")
                else:
                    print("❌ Ollama connection failed!")
                
                if os.path.exists(temp_img_path):
                    os.remove(temp_img_path)

    print("\n🏁 FINAL EXTRACTED TEXT:\n", raw_text[:500], "...\n")
    return jsonify({"status": "success", "extracted_text": raw_text}), 200

if __name__ == '__main__':
    print("🧪 Vision Test Server is listening on port 5002...")
    app.run(host='0.0.0.0', port=5002)