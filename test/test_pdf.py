import PyPDF2

def diagnostic_scan(pdf_path):
    print(f"🔍 Initializing Deep Scan on: {pdf_path}")
    
    try:
        with open(pdf_path, 'rb') as file:
            reader = PyPDF2.PdfReader(file)
            total_pages = len(reader.pages)
            print(f"📄 Found {total_pages} pages.\n")
            
            # We will just test the first 3 pages to see if ANY text exists
            for i in range(min(3, total_pages)):
                page = reader.pages[i]
                text = page.extract_text()
                
                print(f"--- PAGE {i + 1} ---")
                
                # Check if the text is empty or just whitespace/newlines
                if not text or not text.strip():
                    print("🚨 [BLANK] - NO DIGITAL TEXT LAYER DETECTED (This is a scanned image).")
                else:
                    print("✅ TEXT FOUND:")
                    print(text[:200] + "...\n") # Print just the first 200 characters

    except Exception as e:
        print(f"❌ Critical Failure: {e}")

# Run the test on the stubborn PDF
diagnostic_scan("Value_Streams_Architecture_Outside-In.pdf")