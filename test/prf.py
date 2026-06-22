from sentence_transformers import SentenceTransformer
from PIL import Image

# 1. Load the Multimodal Vision Embedding Model (CLIP)
print("📥 Downloading/Loading CLIP Vision Embedding Model...")
model = SentenceTransformer('clip-ViT-B-32')

# 2. Load one of your scanned PDF pages (as an image)
print("👁️ Looking at the architectural diagram...")
img = Image.open('test_page_0.png') # <-- CHANGE THIS to your actual image file

# 3. Generate the Embedding
print("⚙️ Generating Embedding...")
img_embedding = model.encode(img)

# 4. Print the undeniable proof for your dosen
print("\n" + "="*50)
print("🚨 EMBEDDING OUTPUT REVEALED 🚨")
print("="*50)
print(f"DataType: {type(img_embedding)}")
print(f"Total Dimensions (Length): {len(img_embedding)} numbers")
print("\nWhat the model actually 'read' from the page:")
print(f"{img_embedding[:15]} ... [AND 497 MORE NUMBERS]")
print("="*50)