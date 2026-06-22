from flask import Flask, request, jsonify
# TODO: Import your existing Graphify/Neo4j script logic here!
# import graphify_engine 

app = Flask(__name__)

# This route matches the URL you put in n8n exactly
@app.route('/process_graph', methods=['POST'])
def process_graph():
    # 1. Catch the JSON payload that n8n just threw at us
    data = request.get_json()

    # 2. Safety check: make sure n8n actually sent the 'text' field
    if not data or 'text' not in data:
        return jsonify({"status": "error", "message": "Bro, no text was sent!"}), 400

    # 3. Extract the exact Warhammer lore!
    warhammer_lore = data['text']
    
    print("\n" + "="*50)
    print("🔥 INCOMING LORE CAUGHT FROM N8N! 🔥")
    print(f"Excerpt: {warhammer_lore[:100]}...") # Prints the first 100 characters to prove it worked
    print("="*50 + "\n")

    # ---------------------------------------------------------
    # 🧠 THIS IS WHERE YOUR GRAPHIFY LOGIC GOES!
    # Instead of reading a file, you pass 'warhammer_lore' directly into your graph extractor.
    # Example: graphify_engine.extract_and_save_to_neo4j(warhammer_lore)
    # ---------------------------------------------------------

    # 4. Throw a "Success" message back to n8n so the node turns Green!
    return jsonify({
        "status": "success", 
        "message": "Graphify successfully received the lore and updated the Neo4j Graph!"
    }), 200

if __name__ == '__main__':
    # Start the server on port 5000
    print("🚀 Graphify Webhook is alive and listening on port 5000...")
    app.run(host='0.0.0.0', port=5000)