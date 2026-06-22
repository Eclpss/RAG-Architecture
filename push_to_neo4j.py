import json
from neo4j import GraphDatabase

# --- DOCKER CONNECTION SETTINGS ---
URI = "bolt://localhost:7687" 
USER = "neo4j"
PASSWORD = "password" # <-- CHANGE THIS TO YOUR DOCKER NEO4J PASSWORD

# --- PATH TO YOUR GRAPHIFY JSON ---
JSON_PATH = "./input_docs/graphify-out/graph.json"

def push_to_matrix():
    print("🔌 Connecting to Neo4j Docker Container...")
    driver = GraphDatabase.driver(URI, auth=(USER, PASSWORD))
    
    with open(JSON_PATH, 'r', encoding='utf-8') as f:
        graph_data = json.load(f)
        
    nodes = graph_data.get('nodes', [])
    # BUG FIX 1: Graphify might use 'links' instead of 'edges'
    edges = graph_data.get('edges', graph_data.get('links', [])) 
    
    print(f"📦 Found {len(nodes)} Nodes and {len(edges)} Edges. Commencing upload...")

    with driver.session() as session:
        # 1. WIPE THE DATABASE CLEAN (Fresh Start)
        session.run("MATCH (n) DETACH DELETE n")
        
        # 2. INGEST NODES WITH DYNAMIC COLOR LABELS
        for node in nodes:
            node_id = node.get('id', 'unknown')
            node_name = node.get('label', node_id)
            # BUG FIX 2: Graphify uses 'src' instead of 'source'
            source_file = node.get('src', node.get('source', 'unknown_doc'))
            
            # This creates a clean label (e.g., "toho.txt" becomes "Toho") for automatic coloring!
            clean_label = source_file.replace('.txt', '').replace('.pdf', '').capitalize()
            if not clean_label or clean_label == 'Unknown_doc':
                clean_label = "Entity"

            session.run(f"""
                MERGE (n:{clean_label} {{id: $id}})
                SET n.name = $name, n.source = $source
            """, id=node_id, name=node_name, source=source_file)
            
        # 3. INGEST EDGES
        for edge in edges:
            source_id = edge.get('source')
            target_id = edge.get('target')
            # Look for the relationship name (could be under 'label' or 'type')
            rel_type = edge.get('label', edge.get('type', 'CONNECTED_TO')).replace(' ', '_').upper()
            
            # Notice we don't specify the label here, we just search by ID so it connects perfectly
            query = f"""
                MATCH (a {{id: $source_id}})
                MATCH (b {{id: $target_id}})
                MERGE (a)-[r:{rel_type}]->(b)
            """
            session.run(query, source_id=source_id, target_id=target_id)

    driver.close()
    print("✅ UPLOAD COMPLETE! The Matrix is loaded and color-coded.")

if __name__ == "__main__":
    push_to_matrix()