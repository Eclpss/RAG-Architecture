import chromadb

print("🔌 Connecting to Local ChromaDB Matrix...")

try:
    # Connect to the Chroma Docker container
    client = chromadb.HttpClient(host='localhost', port=8000)
    collections = client.list_collections()
    
    if not collections:
        print("\n⚠️ No databases found! Chroma is empty.")
        exit()

    print(f"\n📂 Found {len(collections)} databases:")
    for col in collections:
        print(f" - {col.name}")

    print("\n-----------------------------------")
    target_name = input("Type the exact name of the database you want to peek into (or press Enter to quit): ")

    if target_name:
        target_collection = client.get_collection(name=target_name)
        count = target_collection.count()
        print(f"\n📊 Collection '{target_name}' contains {count} vector chunks.")
        
        print("\n👀 Peeking at the first 2 chunks:")
        results = target_collection.peek(limit=2)
        
        # Print the text chunks and their metadata
        for i, doc in enumerate(results['documents']):
            print(f"\n--- Chunk {i+1} ---")
            print(f"Metadata (Source): {results['metadatas'][i]}")
            print(f"Text Extract: {doc[:300]}...\n")
            
except Exception as e:
    print(f"\n❌ Error connecting to ChromaDB: {e}")