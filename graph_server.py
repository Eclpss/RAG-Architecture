import os
import pandas as pd
import requests
from flask import Flask, request, jsonify
from neo4j import GraphDatabase

# --- DOCKER CONNECTION SETTINGS ---
URI = "bolt://localhost:7687" 
USER = "neo4j"
PASSWORD = "password"

app = Flask(__name__)

@app.route('/process_csv', methods=['POST'])
def process_csv():
    if 'file' not in request.files:
        return jsonify({"status": "error", "message": "No CSV file sent!"}), 400

    csv_file = request.files['file']
    print(f"\n🔥 [PORT 5003] INCOMING CSV CAUGHT FOR GRAPH: {csv_file.filename} 🔥")

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
    
    Example Output format:
    UNWIND $batch AS row
    MERGE (a:Person {{name: row.Customer_Name}})
    MERGE (b:Item {{name: row.Product_Bought}})
    MERGE (a)-[:PURCHASED]->(b)
    
    ONLY output the raw Cypher query code. Do not include markdown blocks (like ```cypher), do not include any conversational text.
    """

    try:
        response = requests.post("http://localhost:11434/api/generate", json={
            "model": "gemma4:latest", 
            "prompt": prompt,
            "stream": False
        })
        
        raw_cypher = response.json().get("response", "")
        clean_cypher = raw_cypher.replace("```cypher", "").replace("```", "").strip()
        
        print(f"📐 Gemma's Blueprint:\n{clean_cypher}\n")
        
    except Exception as e:
        return jsonify({"status": "error", "message": f"Failed to get Blueprint from Gemma: {e}"}), 500

    # ---------------------------------------------------------
    # 🚀 THE UNWIND MACHINE GUN 
    # ---------------------------------------------------------
    print("🔌 Uploading to Neo4j using the dynamic blueprint...")
    driver = GraphDatabase.driver(URI, auth=(USER, PASSWORD))
    
    with driver.session() as session:
        # 🔥 DROPPED BATCH SIZE TO 1000 SO YOUR LAPTOP DOES NOT EXPLODE
        batch_size = 1000 
        total_rows = len(records)
        
        for i in range(0, total_rows, batch_size):
            batch = records[i : i + batch_size]
            try:
                session.run(clean_cypher, batch=batch)
                print(f"✅ Uploaded connected graph chunks {i} to {i + len(batch)} out of {total_rows}")
            except Exception as e:
                print(f"❌ Neo4j crashed on Gemma's code: {e}")
                return jsonify({"status": "error", "message": "Gemma wrote bad Cypher code!"}), 500
                
    driver.close()
    print("🏁 DYNAMIC CSV INGESTION COMPLETE!")
    return jsonify({"status": "success", "message": f"Successfully ingested {total_rows} rows with AI Relationships!"}), 200

if __name__ == '__main__':
    print("🚀 Dedicated Neo4j Graph Builder is listening on port 5003...")
    app.run(host='0.0.0.0', port=5003)