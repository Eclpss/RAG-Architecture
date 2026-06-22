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


# --- DOCKER CONNECTION SETTINGS ---
URI = "bolt://localhost:7687" 
USER = "neo4j"
PASSWORD = "password"

app = Flask(__name__)

import tempfile
import uuid
import shutil

# Notice we added json_path as a parameter so it never looks for a hardcoded folder!
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
# Force the label to start with a letter (Doc_) and strip out weird characters
    import re
    clean_label = "Doc_" + re.sub(r'[^a-zA-Z0-9_]', '', custom_title.replace(" ", "_"))
    if not clean_label or clean_label == 'Unknown_doc':
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


@app.route('/process_graph', methods=['POST'])
def process_graph():
    if 'file' not in request.files:
        return jsonify({"status": "error", "message": "No PDF file sent!"}), 400

    pdf_file = request.files['file']
    doc_title = request.form.get('title', 'Unknown_Lore')
    
    # 🧠 DYNAMIC PATH GENERATION: Creates a unique, invisible folder for this exact job!
    job_id = str(uuid.uuid4())
    work_dir = os.path.join(tempfile.gettempdir(), f"rag_job_{job_id}")
    os.makedirs(work_dir, exist_ok=True)
    
    print(f"\n🔥 INCOMING PDF CAUGHT FROM N8N: {doc_title} | Workspace: {work_dir} 🔥")

    temp_pdf_path = os.path.join(work_dir, "temp.pdf")
    pdf_file.save(temp_pdf_path)

    # 1. NORMAL FAST EXTRACTION
    raw_text = ""
    try:
        with fitz.open(temp_pdf_path) as doc:
            for page in doc:
                raw_text += page.get_text()
    except Exception as e:
        return jsonify({"status": "error", "message": "Failed to read PDF fonts."}), 500

    # 2. THE SMART ROUTER (VISION FALLBACK)
    if len(raw_text.strip()) < 50:
        print("🚨 SCANNED PDF DETECTED! Engaging Qwen-VL Vision Fallback...")
        raw_text = ""
        with fitz.open(temp_pdf_path) as doc:
            for page in doc:
                pix = page.get_pixmap(dpi=50, colorspace=fitz.csGRAY) 
                temp_img_path = os.path.join(work_dir, f"temp_page_{page.number}.png")
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

    # 3. SAVE TEXT AND HANDOFF TO GRAPHIFY (USING GEMMA 4)
    input_filepath = os.path.join(work_dir, "n8n_document.txt")
    with open(input_filepath, "w", encoding="utf-8") as f:
        f.write(raw_text)

    print("⏳ Waking up Gemma 4 to extract the knowledge graph...")
    try:
        extracted_data = llm.extract_corpus_parallel(
            files=[Path(input_filepath)],
            backend="kimi", 
            model="gemma4:latest", # <--- LOCKED TO GEMMA 4 LATEST
            api_key="ollama_does_not_care", 
            root=Path(work_dir)
        )

        out_dir = os.path.join(work_dir, "graphify-out")
        os.makedirs(out_dir, exist_ok=True)
        dynamic_json_path = os.path.join(out_dir, "graph.json")
        
        with open(dynamic_json_path, "w", encoding="utf-8") as f:
            json.dump(extracted_data, f, indent=2)

    except Exception as e:
        shutil.rmtree(work_dir, ignore_errors=True) # Cleanup on fail
        return jsonify({"status": "error", "message": f"Extraction failed: {e}"}), 500

    # 4. PUSH TO NEO4J
    success = push_to_matrix(doc_title, dynamic_json_path)
    
    # 🧹 CRITICAL: Delete the temporary ghost folder so the hard drive doesn't fill up!
    shutil.rmtree(work_dir, ignore_errors=True)
    
    if success:
        return jsonify({"status": "success", "text": raw_text}), 200
    else:
        return jsonify({"status": "error", "message": "Upload to Neo4j failed!"}), 500
  # Notice how this next line is tight against the left wall!
@app.route('/process_csv', methods=['POST'])
def process_csv():
    if 'file' not in request.files:
        return jsonify({"status": "error", "message": "No CSV file sent!"}), 400

    csv_file = request.files['file']
    print(f"\n🔥 INCOMING CSV CAUGHT: {csv_file.filename} 🔥")

    # 1. Read the massive CSV with Pandas
    import pandas as pd
    import requests
    import re
    
    df = pd.read_csv(csv_file, low_memory=False)
    
    # Clean the column names so they are safe for Neo4j and Gemma
    df.columns = [c.replace(' ', '_').replace('-', '_') for c in df.columns]
    
    # 🛡️ THE MATH ARMOR: Fill blanks safely
    for col in df.columns:
        if pd.api.types.is_numeric_dtype(df[col]):
            df[col] = df[col].fillna(0) 
        else:
            df[col] = df[col].fillna("Unknown") 
            
    records = df.to_dict('records') 
    headers = list(df.columns)

    # ---------------------------------------------------------
    # 🧠 THE SCHEMA ARCHITECT: Asking Gemma to build the Graph
    # ---------------------------------------------------------
    print(f"🧠 Asking Gemma to Architect the Schema for headers: {headers} ...")
    
    prompt = f"""
    You are an expert Neo4j Database Architect. 
    I have a CSV file with the following columns: {headers}
    
    Write a single Neo4j Cypher query that takes a batch of rows and creates meaningful Nodes and Relationships between them.
    
    RULES:
    1. You MUST use this exact starting line: UNWIND $batch AS row
    2. You MUST use MERGE to prevent duplicates.
    3. Make sure to reference the columns exactly as they are named in the list using `row.COLUMN_NAME`.
    4. CRITICAL: DO NOT use any Neo4j casting functions (like date(), datetime(), toInteger(), toFloat(), etc.). Assign the properties exactly as they are without wrapping them in functions.
    5. CRITICAL SYNTAX: Once you bind a variable to a node (e.g., MERGE (a:Person {{name: row.Customer_Name}})), you MUST NOT re-declare its labels or properties later in the query. Just use the isolated variable name for relationships: MERGE (a)-[:PURCHASED]->(b).
    
    Example Output format:
    UNWIND $batch AS row
    MERGE (a:Person {{name: row.Customer_Name}})
    MERGE (b:Item {{name: row.Product_Bought}})
    MERGE (a)-[:PURCHASED]->(b)
    
    ONLY output the raw Cypher query code. Do not include markdown blocks (like ```cypher), do not include any conversational text.
    """

    try:
        response = requests.post("http://localhost:11434/api/generate", json={
            "model": "ibm/granite4.1:8b", # Change this if your local model has a different name
            "prompt": prompt,
            "stream": False
        })
        
        raw_cypher = response.json().get("response", "")
        # Clean up any markdown tags Gemma might accidentally include
        clean_cypher = raw_cypher.replace("```cypher", "").replace("```", "").strip()
        
        print(f"📐 Gemma's Blueprint:\n{clean_cypher}\n")
        
    except Exception as e:
        return jsonify({"status": "error", "message": f"Failed to get Blueprint from Gemma: {e}"}), 500

    # ---------------------------------------------------------
    # 🚀 THE UNWIND MACHINE GUN (Using Gemma's Blueprint)
    # ---------------------------------------------------------
    print("🔌 Uploading to Neo4j using the dynamic blueprint...")
    from neo4j import GraphDatabase
    driver = GraphDatabase.driver(URI, auth=(USER, PASSWORD))
    
    with driver.session() as session:
        batch_size = 1000
        total_rows = len(records)
        
        for i in range(0, total_rows, batch_size):
            batch = records[i : i + batch_size]
            try:
                # Execute the code Gemma just wrote!
                session.run(clean_cypher, batch=batch)
                print(f"✅ Uploaded connected graph chunks {i} to {i + len(batch)} out of {total_rows}")
            except Exception as e:
                print(f"❌ Neo4j crashed on Gemma's code: {e}")
                return jsonify({"status": "error", "message": "Gemma wrote bad Cypher code!"}), 500
                
    driver.close()
    print("🏁 DYNAMIC CSV INGESTION COMPLETE!")
    return jsonify({"status": "success", "message": f"Successfully ingested {total_rows} rows with AI Relationships!"}), 200

# --- THE BACKGROUND WORKER ---
# Added 'original_filename' so we know exactly which CSV the row came from!
def background_vector_job(file_path, db_title, original_filename):
    import pandas as pd
    import chromadb
    from chromadb.utils import embedding_functions
    import time
    import re

    clean_db_name = re.sub(r'[^a-zA-Z0-9_-]', '_', db_title).strip('_').lower()
    if len(clean_db_name) < 3:
        clean_db_name = "default_csv_db"

    print(f"\n[BACKGROUND WORKER] 🚀 Speed-Loader engaged for Database: '{clean_db_name}'...")
    
    client = chromadb.HttpClient(host='localhost', port=8000)
    ollama_ef = embedding_functions.OllamaEmbeddingFunction(
        url="http://localhost:11434/api/embeddings",
        model_name="qwen3-embedding:0.6b" 
    )
    
    # This automatically connects to the same DB if it already exists!
    collection = client.get_or_create_collection(name=clean_db_name, embedding_function=ollama_ef)

    print(f"[BACKGROUND WORKER] ⏳ Reading CSV into memory...")
    df = pd.read_csv(file_path, low_memory=False)
    
    for col in df.columns:
        if pd.api.types.is_numeric_dtype(df[col]):
            df[col] = df[col].fillna(0)
        else:
            df[col] = df[col].fillna("Unknown")
            
    documents, ids, metadatas = [], [], []
    for idx, row in df.iterrows():
        parts = [f"{str(k)}: {str(v)}" for k, v in row.items() if v != "Unknown" and str(v).strip() != ""]
        if parts:
            documents.append("Record data -> " + " | ".join(parts) + ".")
            # Added the filename to the ID so row_1 in customers doesn't overwrite row_1 in products!
            ids.append(f"{original_filename}_row_{idx}")
            
            # 🔥 DYNAMIC SOURCE: Tags it with the REAL filename!
            metadatas.append({"source": original_filename})

    total_rows = len(documents)
    print(f"[BACKGROUND WORKER] ✅ Translation complete. Uploading {total_rows} rows...")

    batch_size = 100
    start_time = time.time()
    for i in range(0, total_rows, batch_size):
        end_idx = min(i + batch_size, total_rows)
        collection.upsert(
            documents=documents[i:end_idx],
            ids=ids[i:end_idx],
            metadatas=metadatas[i:end_idx]
        )
        print(f"[BACKGROUND WORKER] 🔥 Uploaded vectors {i} to {end_idx} out of {total_rows}...")

    end_time = time.time()
    print(f"[BACKGROUND WORKER] 🏁 DONE! Vector Matrix '{clean_db_name}' updated in {round((end_time - start_time) / 60, 2)} minutes.")


# --- THE N8N WEBHOOK ENDPOINT ---
@app.route('/embed_csv', methods=['POST'])
def embed_csv():
    if 'file' not in request.files:
        return jsonify({"status": "error", "message": "No file sent!"}), 400

    csv_file = request.files['file']
    
    # Grab the target DB name from n8n, but keep the real filename separate!
    db_title = request.form.get('title', 'supply_chain_db')
    original_filename = csv_file.filename
    
    print(f"\n🔥 INCOMING N8N VECTOR REQUEST: {original_filename} (Target DB: {db_title}) 🔥")

    temp_path = os.path.join("./input_docs", "vector_temp.csv")
    csv_file.save(temp_path)

    import threading
    # Pass BOTH the DB name and the real filename to the worker
    thread = threading.Thread(target=background_vector_job, args=(temp_path, db_title, original_filename))
    thread.start()

    return jsonify({"status": "success", "message": f"File received! Python is embedding into '{db_title}' in the background."}), 200


@app.route('/parse_csv_for_n8n', methods=['POST'])
def parse_csv_for_n8n():
    if 'file' not in request.files:
        return jsonify({"error": "No file sent!"}), 400

    csv_file = request.files['file']
    original_filename = csv_file.filename
    
    print(f"\n🔥 TRANSLATING CSV FOR N8N PIPELINE: {original_filename} 🔥")

    import pandas as pd
    import json
    
    try:
        df = pd.read_csv(csv_file, low_memory=False)
        
        # Clean Data
        for col in df.columns:
            if pd.api.types.is_numeric_dtype(df[col]):
                df[col] = df[col].fillna(0)
            else:
                df[col] = df[col].fillna("Unknown")
                
        n8n_items = []
        
        for idx, row in df.iterrows():
            row_dict = {str(k): v for k, v in row.items() if v != "Unknown" and str(v).strip() != ""}
            
            if row_dict:
                # 1. 'text' is the raw JSON string you asked for.
                # 2. 'source_file' will be scooped up by n8n as metadata.
                n8n_items.append({
                    "text": json.dumps(row_dict),
                    "source_file": original_filename
                })
                
        # CRITICAL: We return a FLAT ARRAY here. 
        # No {"status": "success"} wrapper, so n8n splits it into individual items automatically!
        return jsonify(n8n_items), 200

    except Exception as e:
        print(f"❌ Translation failed: {e}")
        return jsonify({"error": str(e)}), 500
    
 
    # =========================================================
# 🚀 THE HIGH-SPEED BULK LANE (BYPASSES N8N SLOWNESS)
# =========================================================
def background_fast_lane_worker(file_path, db_title, original_filename):
    import pandas as pd
    import chromadb
    from chromadb.utils import embedding_functions
    import time
    import json
    import re
    import os

    # Clean the DB name you type in the n8n form
    clean_db_name = re.sub(r'[^a-zA-Z0-9_-]', '_', db_title).strip('_').lower()
    
    print(f"\n[FAST LANE] 🚀 Engaging Python Speed-Loader for '{clean_db_name}'...")
    
    client = chromadb.HttpClient(host='localhost', port=8000)
    ollama_ef = embedding_functions.OllamaEmbeddingFunction(
        url="http://localhost:11434/api/embeddings",
        model_name="qwen3-embedding:0.6b" 
    )
    
    collection = client.get_or_create_collection(name=clean_db_name, embedding_function=ollama_ef)

    print(f"[FAST LANE] ⏳ Reading massive file {original_filename}...")
    df = pd.read_csv(file_path, low_memory=False)
    
    for col in df.columns:
        if pd.api.types.is_numeric_dtype(df[col]):
            df[col] = df[col].fillna(0)
        else:
            df[col] = df[col].fillna("Unknown")
            
    documents, ids, metadatas = [], [], []
    for idx, row in df.iterrows():
        row_dict = {str(k): v for k, v in row.items() if v != "Unknown" and str(v).strip() != ""}
        
        if row_dict:
            # 1. TEXT = RAW JSON
            documents.append(json.dumps(row_dict))
            
            # 2. METADATA = SOURCE FILE
            ids.append(f"{original_filename}_fastlane_{idx}")
            metadatas.append({"source": original_filename})

    total_rows = len(documents)
    print(f"[FAST LANE] ✅ Loaded {total_rows} items in memory. Firing embeddings...")


    batch_size = 250  # Larger batch size for speed!
    start_time = time.time()
    
    for i in range(0, total_rows, batch_size):
        end_idx = min(i + batch_size, total_rows)
        collection.upsert(
            documents=documents[i:end_idx],
            ids=ids[i:end_idx],
            metadatas=metadatas[i:end_idx]
        )
        print(f"[FAST LANE] 🔥 Embedded & Upserted rows {i} to {end_idx}...")

    end_time = time.time()
    print(f"[FAST LANE] 🏁 DONE! {total_rows} rows injected into '{clean_db_name}' in {round((end_time - start_time), 2)} seconds!")
    
    if os.path.exists(file_path):
        os.remove(file_path)

@app.route('/bulk_fast_lane', methods=['POST'])
def bulk_fast_lane():
    if 'file' not in request.files:
        return jsonify({"error": "No file sent!"}), 400

    csv_file = request.files['file']
    
    # 🔥 FIX: Dynamically grab the title from the n8n form! (Defaults to enterprise_db if empty)
    db_title = request.form.get('title', 'enterprise_db') 
    
    original_filename = csv_file.filename
    print(f"\n🔥 INCOMING FAST LANE REQUEST: {original_filename} (Target DB: {db_title}) 🔥")

    # Dynamic Pathing
    job_id = str(uuid.uuid4())
    work_dir = os.path.join(tempfile.gettempdir(), f"csv_job_{job_id}")
    os.makedirs(work_dir, exist_ok=True)
    
    temp_path = os.path.join(work_dir, f"fastlane_{original_filename}")
    csv_file.save(temp_path)

    import threading
    thread = threading.Thread(target=background_fast_lane_worker, args=(temp_path, db_title, original_filename))
    thread.start()

    return jsonify({
        "status": "success", 
        "message": f"File received! Embedding rows into '{db_title}' at high speed."
    }), 200
    
    # =========================================================
# 📂 THE BATCH FOLDER PROCESSOR (BYPASSES DOCKER TRAP)
# =========================================================
@app.route('/process_folder_batch', methods=['POST'])
def process_folder_batch():
    data = request.get_json(silent=True) or {}
    folder_path = data.get('folder_path')
    db_title = data.get('title', 'Batch_Matrix')

    if not folder_path or not os.path.exists(folder_path):
        return jsonify({"status": "error", "message": f"Folder not found on host machine: {folder_path}"}), 400

    print(f"\n🔥 INCOMING BATCH REQUEST! Scanning host folder: {folder_path} for DB: {db_title} 🔥")

    processed_count = 0
    
    # Loop through all files in the directory natively on Windows!
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

            # --- GRAPHIFY GEMMA 4 EXTRACTION ---
            temp_txt_path = "./n8n_document.txt"
            with open(temp_txt_path, "w", encoding="utf-8") as f:
                f.write(raw_text)

            print(f"⏳ Waking up Gemma 2 for {filename}...")
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
# 📡 THE RADAR: Tells n8n what databases already exist
# =========================================================
@app.route('/list_databases', methods=['GET'])
def list_databases():
    import chromadb
    try:
        client = chromadb.HttpClient(host='localhost', port=8000)
        collections = client.list_collections()
        
        # Grab all the names
        db_names = [c.name for c in collections]
        
        # We add this so n8n always has a "Create New" option in the dropdown!
        db_names.insert(0, "➕ CREATE NEW DATABASE")
        
        return jsonify(db_names), 200
    except Exception as e:
        print(f"❌ Failed to ping ChromaDB: {e}")
        return jsonify(["➕ CREATE NEW DATABASE", "enterprise_db", "sales_db"]), 200
    
if __name__ == '__main__':
    print("🚀 PyMuPDF + Qwen Vision + Graphify Bridge is listening on port 5000...")
    app.run(host='0.0.0.0', port=5000)