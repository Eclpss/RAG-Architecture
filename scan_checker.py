import os
import fitz  # PyMuPDF

def find_scanned_pdfs(directory_path):
    scanned_pdfs = []
    readable_pdfs = []
    error_pdfs = []

    print(f"🔍 Scanning all PDFs in: {directory_path}...\n")

    if not os.path.exists(directory_path):
        print("❌ ERROR: Path does not exist. Check your folder path!")
        return

    for filename in os.listdir(directory_path):
        if filename.lower().endswith('.pdf'):
            file_path = os.path.join(directory_path, filename)
            try:
                with fitz.open(file_path) as doc:
                    text = ""
                    # We only need to check the first 3 pages to know if it's text or images
                    num_pages_to_check = min(3, len(doc))
                    for i in range(num_pages_to_check):
                        text += doc[i].get_text().strip()

                    # If there's barely any text (less than 50 characters), it's a scanned image
                    if len(text) < 50:
                        scanned_pdfs.append(filename)
                    else:
                        readable_pdfs.append(filename)
            except Exception as e:
                error_pdfs.append(f"{filename} (Error: {e})")

    # --- PRINT THE RESULTS ---
    print("🚨 REQUIRES VISION AI (Scanned PDFs):")
    if not scanned_pdfs:
        print("  None found! They are all text-readable.")
    else:
        for pdf in scanned_pdfs:
            print(f"  - {pdf}")

    print(f"\n✅ TEXT READABLE: {len(readable_pdfs)} files")
    
    if error_pdfs:
        print(f"\n⚠️ CORRUPTED / UNREADABLE: {len(error_pdfs)} files")
        for pdf in error_pdfs:
            print(f"  - {pdf}")

# Set your target path here! (Using 'r' before the string handles Windows backslashes)
target_folder = r"C:\Users\herup\Documents\Datasets\sorted"
find_scanned_pdfs(target_folder)