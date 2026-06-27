import requests
from flask import Flask, request, jsonify
from neo4j import GraphDatabase

app = Flask(__name__)

# --- NEO4J CONNECTION ---
NEO4J_URI = "bolt://localhost:7687"
NEO4J_USER = "neo4j"
NEO4J_PASSWORD = "password" # <--- CHANGE THIS IF NEEDED!

driver = GraphDatabase.driver(NEO4J_URI, auth=(NEO4J_USER, NEO4J_PASSWORD))

@app.route('/ask_neo4j', methods=['POST'])
def ask_neo4j():
    # 🛡️ THE SHIELD: Forgive bad JSON and mismatched keys from n8n/AnythingLLM
    data = request.get_json(silent=True) or {}
    question = data.get("question", "") or data.get("query", "") or data.get("text", "")
    
    if not question:
        question = request.data.decode("utf-8")
        if not question or len(question) < 2:
            return jsonify({ "text": "n8n failed to send a valid question payload." }), 400

    print(f"\n🤖 [NEO4J AGENT] Incoming Question: {question}")

    with driver.session() as session:
        try:
            # 🔥 THE UNIVERSAL TOPOLOGY SCANNER: Reads the exact map of ANY database
            # 1. Get exact valid paths (Node -> Relationship -> Node)
            path_result = session.run("MATCH (a)-[r]->(b) RETURN DISTINCT labels(a)[0] AS From, type(r) AS Rel, labels(b)[0] AS To LIMIT 200")
            valid_paths = [f"({r['From']})-[:{r['Rel']}]->({r['To']})" for r in path_result]
            
            # 2. Get exact properties mapped specifically to each node label
            prop_result = session.run("""
                CALL db.schema.nodeTypeProperties() 
                YIELD nodeLabels, propertyName 
                RETURN nodeLabels[0] AS label, collect(DISTINCT propertyName) AS props
            """)
            node_props = [f"Node '{r['label']}' contains properties: {r['props']}" for r in prop_result if r['label']]
            
        except Exception as e:
            return jsonify({ "text": f"Database scan failed: {e}" }), 500

        # 🧠 THE UNIVERSAL BRAIN (TWO-LANE SYSTEM)
        prompt = f"""
        You are an expert Neo4j Database Query writer.
        Translate the user's question into a single, valid Cypher query.
        
        CRITICAL RULES:
        1. You MUST ONLY use the schema map provided below. Do not guess or invent property names.
        
        === DYNAMIC GRAPH TOPOLOGY MAP ===
        Valid Node-to-Node Relationships:
        {valid_paths}
        
        Exact Properties mapped to Nodes:
        {node_props}
        ==================================

        2. 📄 DOCUMENT COUNTING RULE: If the user searches for a keyword (like 'vision') across documents, you MUST use this exact chunk-counting pattern (replace 'the_word_here'):
           MATCH (doc:Document)-[:CONTAINS_CHUNK]->(chunk:Chunk)
           WHERE toLower(chunk.text) CONTAINS toLower('the_word_here') OR toLower(chunk.description) CONTAINS toLower('the_word_here')
           RETURN doc.name AS Document_Name, count(chunk) AS Mentions
           ORDER BY Mentions DESC

        3. 🕸️ ERP / RELATIONSHIP RULE: If the user asks about specific entities, follow the 'Valid Relationships' paths.
        
        4. 📊 DATA ANALYTICS & SEGMENTATION RULE: If the user asks to "Analyze Customer Segmentation Grouping" or calculate sales/profits against orders, you MUST use aggregate math functions (SUM, toInteger). 
           Use this exact pattern based on the schema mapping:
           MATCH (c:Customer)-[:PLACED_ORDER]->(o:Order)
           RETURN c.Industry AS Industry, c.Market_Segment AS Segment, sum(toInteger(o.Order_Total)) AS Total_Sales, sum(toInteger(o.Profit_Per_Order)) AS Total_Profit
           ORDER BY Total_Sales DESC

        5. 🛑 SYNTAX & OUT-OF-SCOPE SHIELD: 
           - NEVER use dynamic variables (like `+`) inside Node Labels. `(t:Table)` is valid, `(t:+name+)` is fatal.
           - If the user asks for "definitions", "column meanings", or dictionary metadata, output EXACTLY:
             RETURN 'Definition not found in the Graph Matrix. Please ask the Vector Database for data dictionary definitions.' AS Message

        6. 🛑 INCOMPLETE QUESTION SHIELD: If the user's question is cut off, output EXACTLY:
           RETURN 'The question was cut off by the system before reaching the database.' AS Error_Message

        7. 🛑 STRICT CYPHER SYNTAX RULE: You MUST follow the exact Neo4j execution order: MATCH -> WHERE -> WITH -> RETURN -> ORDER BY -> LIMIT. NEVER, under any circumstances, place a WHERE clause AFTER a RETURN clause.

        8. 🛑 ANTI-HALLUCINATION RULE: NEVER invent node labels. You must strictly use ONLY the exact Node Labels provided in the 'DYNAMIC GRAPH TOPOLOGY MAP' above. Ignore any unrelated lore or memory.

        9. 🔗 FLEXIBLE PATH RULE: If you are unsure of the exact relationship path between two concepts, use a flexible path search instead of complex arrays. 
           Example: MATCH (a)-[*1..3]-(b) WHERE toLower(a.id) CONTAINS toLower('keyword') RETURN a, b

        10. Return ONLY the raw Cypher code. No markdown formatting, no conversational text.
        
        11. Always append `LIMIT 25` to the very end of your query (unless using Rule 5 or 6).
        
        User Question: "{question}"
        """
        
        print(f"🧠 [NEO4J AGENT] Asking  to translate English to Cypher...")
        try:
            response = requests.post("http://localhost:11434/api/generate", json={
                "model": "ibm/granite4.1:8b", 
                "prompt": prompt,
                "stream": False
            })
            raw_cypher = response.json().get("response", "")
            
            # 🔥 THIS MUST BE EXACTLY ONE SINGLE LINE:
            clean_cypher = raw_cypher.replace("```cypher", "").replace("```", "").strip()
            
            print(f"📐 [NEO4J AGENT]  Cypher Code:\n{clean_cypher}")
            
        except Exception as e:
            return jsonify({ "text": f"Failed to contact local : {e}" }), 500

        # --- 3. THE EXECUTION ---
        try:
            result = session.run(clean_cypher)
            records = [record.data() for record in result]
            
            if not records:
                final_answer = "I searched the Graph Matrix, but could not find any exact data matching your question."
            else:
                final_answer = "Data found in Neo4j Knowledge Graph:\n\n"
                for r in records:
                    final_answer += f"- {r}\n"
            
            print("✅ [NEO4J AGENT] Query successful! Handing data back to UI.")
            return jsonify({ "text": final_answer }), 200

        except Exception as e:
            print(f"❌ [NEO4J AGENT] Execution failed.  wrote bad code: {e}")
            return jsonify({ "text": f"The AI attempted to run this Cypher query but failed: {clean_cypher}\n\nError: {e}" }), 500

if __name__ == '__main__':
    print("🕸️ Neo4j Smart Agent is listening on port 5001...")
    app.run(host='0.0.0.0', port=5001, debug=True, use_reloader=False)
