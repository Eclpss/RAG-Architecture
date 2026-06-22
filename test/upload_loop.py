import os
import requests
import time

# 1. Your exact folder path for the sorted PDFs
folder_path = r"C:\Users\herup\Documents\Datasets\sorted"

# 2. Your n8n Test Webhook URL (Assuming default port 5678)
webhook_url = "http://localhost:5678/webhook/bulk-ingest"

print(f"📂 Scanning folder: {folder_path}...")

# 3. Loop through the folder
for filename in os.listdir(folder_path):
    if filename.lower().endswith(".pdf"):
        file_path = os.path.join(folder_path, filename)
        print(f"🚀 Injecting: {filename}...")
        
        # Open the PDF and shoot it to n8n
        try:
            with open(file_path, "rb") as f:
                # We package it as "data" so your Default Data Loader catches it perfectly!
                files = {"my_pdf": (filename, f, "application/pdf")}
                response = requests.post(webhook_url, files=files)
                
            if response.status_code == 200:
                print(f"✅ Success! (Status: {response.status_code})")
            else:
                print(f"❌ Failed! (Status: {response.status_code}) - {response.text}")
                
        except Exception as e:
            print(f"⚠️ Error uploading {filename}: {e}")
            
        # 4. THE COOLDOWN: Wait 3 seconds so your RAM and Qwen don't crash!
        time.sleep(3) 

print("🎉 ALL PDFs UPLOADED SUCCESSFULLY! THE VECTOR BRAIN IS FULL!")