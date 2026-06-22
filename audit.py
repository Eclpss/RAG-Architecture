import os
import csv

# --- 1. SET YOUR PATHS ---
# Replace this with the actual folder path where your 152 PDFs live
pdf_folder = r"C:\Users\herup\Documents\Datasets\sorted" 
csv_file = "FULL_MATRIX_DUMP.csv"

print("🔍 Auditing the Matrix...")

# --- 2. GET ORIGINAL PDFs ---
all_pdfs = set([f for f in os.listdir(pdf_folder) if f.lower().endswith('.pdf')])

# --- 3. GET SAVED PDFs FROM CSV ---
saved_pdfs = set()
try:
    with open(csv_file, 'r', encoding='utf-8') as f:
        reader = csv.DictReader(f)
        for row in reader:
            # Matches the exact column name you used in Neo4j
            saved_pdfs.add(row['Source File']) 
except FileNotFoundError:
    print("❌ Cannot find FULL_MATRIX_DUMP.csv in this folder!")
    exit()

# --- 4. FIND THE MISSING ONES ---
missing_pdfs = all_pdfs - saved_pdfs

print(f"\n📁 Total Original PDFs in folder: {len(all_pdfs)}")
print(f"💾 Total PDFs successfully in CSV: {len(saved_pdfs)}")

print(f"\n🚨 THE {len(missing_pdfs)} MISSING PDFs:")
print("-" * 40)
for pdf in missing_pdfs:
    print(f"❌ {pdf}")
print("-" * 40)

print("\n💡 TIP: Open a few of these. Are they scanned images instead of text?")