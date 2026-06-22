import streamlit as st
import requests
import chromadb
import json

# --- CONFIGURATION ---
OLLAMA_URL = "http://localhost:11434/api/generate"
NEO4J_API_URL = "http://localhost:5001/ask_neo4j"
LLM_MODEL = "gemma4" # Or gemma4:latest depending on your Ollama tag

# Connect to your local ChromaDB
chroma_client = chromadb.HttpClient(host='localhost', port=8000)
# Make sure to load the exact database we built!
collection = chroma_client.get_collection(name="final_thesis")

st.set_page_config(page_title="Graphify OS", page_icon="🕸️", layout="wide")
st.title("🕸️ Graphify: Multi-Graph RAG Engine")
st.markdown("Bypassing the UI. Direct connection to **ChromaDB**, **Neo4j**, and **Gemma4**.")

# Initialize Chat History
if "messages" not in st.session_state:
    st.session_state.messages = []

# Display Chat History
for message in st.session_state.messages:
    with st.chat_message(message["role"]):
        st.markdown(message["content"])

# --- THE CHAT ENGINE ---
if prompt := st.chat_input("Ask your Thesis Database..."):
    # 1. Show user message
    st.chat_message("user").markdown(prompt)
    st.session_state.messages.append({"role": "user", "content": prompt})

    with st.chat_message("assistant"):
        with st.status("🧠 Querying Multi-Graph Brain...", expanded=True) as status:
            
            # --- PHASE 1: Query Neo4j (Via your Port 5001 API) ---
            st.write("🕷️ Searching Neo4j Relationships...")
            try:
                neo_response = requests.post(NEO4J_API_URL, json={"question": prompt}).json()
                neo_data = neo_response.get("text", "No graph data found.")
            except Exception as e:
                neo_data = f"Neo4j Offline: {e}"

           # --- PHASE 2: Query ChromaDB ---
            st.write("📚 Generating 1024-Dimension Vector...")
            
            # 1. Manually embed the prompt using your local Qwen model via Ollama
            embed_payload = {
                "model": "qwen3-embedding:0.6b",  # ⚠️ CHANGE THIS to your exact Qwen embedding model name in Ollama!
                "prompt": prompt
            }
            
            try:
                embed_response = requests.post("http://localhost:11434/api/embeddings", json=embed_payload).json()
                qwen_vector = embed_response.get("embedding")
                
                # 2. Pass the RAW NUMBERS to Chroma, bypassing the 384-dimension default!
                if qwen_vector:
                    st.write("🔍 Searching Chroma Vector Database...")
                    results = collection.query(
                        query_embeddings=[qwen_vector], 
                        n_results=2
                    )
                    chroma_data = "\n".join(results['documents'][0]) if results['documents'] else "No vector data found."
                else:
                    chroma_data = "Failed to generate embedding vector."
                    
            except Exception as e:
                chroma_data = f"Embedding Error: {e}"
            # --- PHASE 3: The Master Prompt ---
            master_prompt = f"""You are Graphify, a brilliant Multi-Graph AI. 
            Answer the user's question using ONLY the context provided below.
            
            [NEO4J GRAPH RELATIONSHIPS]:
            {neo_data}
            
            [CHROMA VECTOR DOCUMENTS]:
            {chroma_data}
            
            User Question: {prompt}
            Answer:"""

            # --- PHASE 4: Stream from Ollama ---
            payload = {
                "model": LLM_MODEL,
                "prompt": master_prompt,
                "stream": False # Set to True if you want to handle streaming chunks
            }
            llm_response = requests.post(OLLAMA_URL, json=payload).json()
            final_answer = llm_response.get("response", "LLM failed to answer.")
            
            status.update(label="Response Generated!", state="complete", expanded=False)

        # Show final answer
        st.markdown(final_answer)
        st.session_state.messages.append({"role": "assistant", "content": final_answer})