import chromadb
import pandas as pd

print("🔌 Connecting to the Matrix...")

# Connect to Chroma
client = chromadb.HttpClient(host='localhost', port=8000)
collection = client.get_collection(name="final_thesis")

# .get() pulls ALL data in the database
print("📥 Downloading ALL database chunks into memory...")
results = collection.get()

total_chunks = len(results['documents'])
print(f"✅ Successfully loaded all {total_chunks} chunks.")

# Format the raw JSON data into a clean Pandas DataFrame
print("⏳ Formatting data...")
df = pd.DataFrame({
    "Chunk ID": results["ids"],
    "Source File": [meta.get('source', 'Unknown') for meta in results["metadatas"]],
    "Extracted Text": results["documents"]
})

# Export to CSV (index=False prevents it from writing row numbers)
csv_filename = "FULL_MATRIX_DUMP.csv"
print(f"💾 Exporting to {csv_filename}...")
df.to_csv(csv_filename, index=False)

print(f"🎉 SUCCESS! All {total_chunks} chunks have been saved to {csv_filename}")