import os
import json
import base64
import requests
import fitz  
import threading
from flask import Flask, request, jsonify
from neo4j import GraphDatabase
from pathlib import Path
from graphify import llm  
import tempfile
import uuid
import shutil
import re
import pandas as pd
import chromadb
from chromadb.utils import embedding_functions
import time

# --- DOCKER CONNECTION SETTINGS ---
URI = "bolt://localhost:7687" 
USER = "neo4j"
PASSWORD = "password"

# 🆕 Dynamic Host Configuration (No Hardcoding Rule)
CHROMA_HOST = os.environ.get("CHROMA_HOST", "127.0.0.1")

app = Flask(__name__)

# =========================================================
# 🔗 NEO4J GRAPH PUSHER
# =========================================================
def push_to_matrix(custom_title, json_path):
    print(f"🔌 Connecting to Neo4j Docker Container...")
    driver = GraphDatabase.driver(URI, auth=(USER, PASSWORD))
    
    if not os.path.exists(json_path):
        print(f"❌ ERROR: {json_path} not found!")
        return False

    with open(json_path, 'r', encoding='utf-8') as f:
        graph_data = json.load(f)
        
    nodes = graph_data.get('nodes', [])
    edges = graph_data.get('edges', graph_data.get('links', [])) 
    
    print(f"📦 Found {len(nodes)} Nodes and {len(edges)} Edges. Commencing upload...")

    # 🔥 FIX: Force the label to start with a letter (Doc_) and strip out weird characters
    clean_label = "Doc_" + re.sub(r'[^a-zA-Z0-9_]', '', custom_title.replace(" ", "_"))
    if not clean_label or clean_label == 'Doc_Unknown_doc':
        clean_label = "Entity"

    with driver.session() as session:
        for node in nodes:
            node_id = node.get('id', 'unknown')
            node_name = node.get('label', node_id)
            node_desc = node.get('description', node.get('text', node.get('summary', 'Lore missing.')))
            source_file = custom_title + ".pdf"

            session.run(f"""
                MERGE (n:{clean_label} {{id: $id}})
                SET n.name = $name, n.source = $source, n.description = $desc
            """, id=node_id, name=node_name, source=source_file, desc=node_desc)
            
        for edge in edges:
            source_id = edge.get('source')
            target_id = edge.get('target')
            if not source_id or not target_id: continue
                
            rel_type = edge.get('label', edge.get('type', 'CONNECTED_TO')).replace(' ', '_').upper()
            query = f"""
                MATCH (a {{id: $source_id}})
                MATCH (b {{id: $target_id}})
                MERGE (a)-[r:{rel_type}]->(b)
            """
            session.run(query, source_id=source_id, target_id=target_id)

    driver.close()
    print(f"✅ UPLOAD COMPLETE! The Matrix is loaded and labeled as: {clean_label}")
    return True

# =========================================================
# 📂 THE BATCH FOLDER PROCESSOR (BYPASSES DOCKER TRAP)
# =========================================================
@app.route('/process_folder_batch', methods=['POST'])
def process_folder_batch():
    data = request.get_json(silent=True) or {}
    folder_path = data.get('folder_path')
    db_title = data.get('title', 'Batch_Matrix')
    
    # 🛡️ THE SAFETY NET: Explicitly declared in the local scope first!
    collection = None

    # ---------------------------------------------------------
    # 🆕 REGISTER IN CHROMADB & PREPARE EMBEDDINGS
    # ---------------------------------------------------------
    try:
        clean_db_name = re.sub(r'[^a-zA-Z0-9_-]', '_', db_title).strip('_').lower()
        if len(clean_db_name) < 3:
            clean_db_name = "default_pdf_db"
            
        client = chromadb.HttpClient(host=CHROMA_HOST, port=8000)
        
        ollama_ef = embedding_functions.OllamaEmbeddingFunction(
            url="http://localhost:11434/api/embeddings",
            model_name="qwen3-embedding:0.6b" 
        )
        
        collection = client.get_or_create_collection(name=clean_db_name, embedding_function=ollama_ef)
        print(f"✅ Registered '{clean_db_name}' in ChromaDB Radar!")
    except Exception as e:
        print(f"⚠️ Could not register in ChromaDB: {e}")

    if not folder_path or not os.path.exists(folder_path):
        return jsonify({"status": "error", "message": f"Folder not found on host machine: {folder_path}"}), 400

    print(f"\n🔥 INCOMING BATCH REQUEST! Scanning host folder: {folder_path} for DB: {db_title} 🔥")

    processed_count = 0
    
    # Loop through all files in the directory natively on Windows
    for filename in os.listdir(folder_path):
        if filename.lower().endswith('.pdf'):
            pdf_path = os.path.join(folder_path, filename)
            print(f"\n📄 Batch Processing: {filename}...")
            
            # --- NORMAL EXTRACTION LOGIC ---
            raw_text = ""
            try:
                with fitz.open(pdf_path) as doc:
                    for page in doc:
                        raw_text += page.get_text()
            except Exception as e:
                print(f"❌ Failed to read {filename}: {e}")
                continue

            # --- SMART ROUTER (VISION) ---
            if len(raw_text.strip()) < 50:
                print("🚨 SCANNED PDF DETECTED! Engaging Qwen-VL Vision Fallback...")
                raw_text = ""
                
                with fitz.open(pdf_path) as doc:
                    for page in doc:
                        pix = page.get_pixmap(dpi=50, colorspace=fitz.csGRAY) 
                        temp_img_path = f"./temp_page_{page.number}.png"
                        pix.save(temp_img_path)

                        with open(temp_img_path, "rb") as img_file:
                            b64_image = base64.b64encode(img_file.read()).decode('utf-8')

                        response = requests.post("http://localhost:11434/api/generate", json={
                            "model": "qwen2.5vl:7b", 
                            "prompt": "OCR ENGINE MODE. Extract all legible text exactly as written. Output RAW TEXT ONLY.",
                            "images": [b64_image],
                            "stream": False,
                            "options": {"temperature": 0.0, "num_predict": 1500}
                        })
                        raw_text += response.json().get("response", "") + "\n\n"
                        if os.path.exists(temp_img_path): os.remove(temp_img_path)
                        
            # --- 🧠 PUSH TO CHROMADB (VECTOR BRAIN) ---
            if raw_text.strip():
                if collection is None:
                    print(f"❌ Skipping Vectors for {filename}: ChromaDB connection failed earlier!")
                else:
                    print(f"🧠 Vectorizing text for {filename}...")
                    chunks = [raw_text[i:i+1000] for i in range(0, len(raw_text), 1000)]
                    chunk_ids = [f"{filename}_chunk_{idx}" for idx in range(len(chunks))]
                    chunk_metas = [{"source": filename} for _ in chunks]
                    
                    try:
                        collection.upsert(documents=chunks, ids=chunk_ids, metadatas=chunk_metas)
                        print(f"✅ Injected {len(chunks)} chunks into ChromaDB!")
                    except Exception as e:
                        print(f"❌ Failed to push vectors to Chroma: {e}")

            # --- GRAPHIFY GEMMA 2:9B EXTRACTION ---
            temp_txt_path = "./n8n_document.txt"
            with open(temp_txt_path, "w", encoding="utf-8") as f:
                f.write(raw_text)

            print(f"⏳ Waking up Gemma 2 (9B) for {filename}...")
            try:
                extracted_data = llm.extract_corpus_parallel(
                    files=[Path(temp_txt_path)],
                    backend="kimi", 
                    model="gemma2:9b", 
                    api_key="ollama", 
                    root=Path("./")
                )
                with open("./graph.json", "w", encoding="utf-8") as f:
                    json.dump(extracted_data, f, indent=2)
                    
                # Push to Neo4j
                push_to_matrix(filename.replace(".pdf", ""), "./graph.json")
                processed_count += 1
            except Exception as e:
                print(f"❌ Graph extraction failed for {filename}: {e}")

    return jsonify({
        "status": "success", 
        "message": f"Successfully processed {processed_count} PDFs into {db_title}!"
    }), 200

# =========================================================
# 🚀 CSV SCHEMA ARCHITECT (GRANITE)
# =========================================================
@app.route('/process_csv', methods=['POST'])
def process_csv():
    if 'file' not in request.files:
        return jsonify({"status": "error", "message": "No CSV file sent!"}), 400

    csv_file = request.files['file']
    print(f"\n🔥 INCOMING CSV CAUGHT: {csv_file.filename} 🔥")

    df = pd.read_csv(csv_file, low_memory=False)
    df.columns = [c.replace(' ', '_').replace('-', '_') for c in df.columns]
    
    for col in df.columns:
        if pd.api.types.is_numeric_dtype(df[col]):
            df[col] = df[col].fillna(0) 
        else:
            df[col] = df[col].fillna("Unknown") 
            
    records = df.to_dict('records') 
    headers = list(df.columns)

    print(f"🧠 Asking Granite 4.1 to Architect the Schema for headers: {headers} ...")
    
    prompt = f"""
    You are an expert Neo4j Database Architect. 
    I have a CSV file with the following columns: {headers}
    
    Write a single Neo4j Cypher query that takes a batch of rows and creates meaningful Nodes and Relationships between them.
    
    RULES:
    1. You MUST use this exact starting line: UNWIND $batch AS row
    2. You MUST use MERGE to prevent duplicates.
    3. Make sure to reference the columns exactly as they are named in the list using `row.COLUMN_NAME`.
    4. CRITICAL: DO NOT use any Neo4j casting functions. Assign the properties exactly as they are.
    5. CRITICAL SYNTAX: Once you bind a variable to a node, you MUST NOT re-declare its labels or properties later in the query.
    
    ONLY output the raw Cypher query code. Do not include markdown blocks, do not include any conversational text.
    """

    try:
        response = requests.post("http://localhost:11434/api/generate", json={
            "model": "ibm/granite4.1:8b", 
            "prompt": prompt,
            "stream": False
        })
        raw_cypher = response.json().get("response", "")
        clean_cypher = raw_cypher.replace("```cypher", "").replace("```", "").strip()
        print(f"📐 Granite's Blueprint:\n{clean_cypher}\n")
    except Exception as e:
        return jsonify({"status": "error", "message": f"Failed to get Blueprint: {e}"}), 500

    print("🔌 Uploading to Neo4j using the dynamic blueprint...")
    driver = GraphDatabase.driver(URI, auth=(USER, PASSWORD))
    
    with driver.session() as session:
        batch_size = 1000
        total_rows = len(records)
        for i in range(0, total_rows, batch_size):
            batch = records[i : i + batch_size]
            try:
                session.run(clean_cypher, batch=batch)
                print(f"✅ Uploaded connected graph chunks {i} to {i + len(batch)}")
            except Exception as e:
                print(f"❌ Neo4j crashed on Cypher code: {e}")
                return jsonify({"status": "error", "message": "Bad Cypher code!"}), 500
                
    driver.close()
    return jsonify({"status": "success", "message": f"Successfully ingested {total_rows} rows!"}), 200

# =========================================================
# 📡 THE RADAR: Tells n8n what databases already exist
# =========================================================
@app.route('/list_databases', methods=['GET'])
def list_databases():
    try:
        client = chromadb.HttpClient(host=CHROMA_HOST, port=8000)
        collections = client.list_collections()
        db_names = [c.name for c in collections]
        db_names.insert(0, "➕ CREATE NEW DATABASE")
        
        return jsonify({"databases": db_names}), 200
    except Exception as e:
        print(f"❌ Failed to ping ChromaDB: {e}")
        return jsonify({"databases": ["➕ CREATE NEW DATABASE", "enterprise_db", "sales_db"]}), 200
    
if __name__ == '__main__':
    print("🚀 Dani's Multi-Agent RAG Engine is listening on port 5000...")
    app.run(host='0.0.0.0', port=5000)