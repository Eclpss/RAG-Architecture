import streamlit as st
import chromadb
import pandas as pd
import requests
import json
from neo4j import GraphDatabase
# --- PAGE SETUP ---
st.set_page_config(page_title="RAG Command Center", page_icon="🧠", layout="wide")
st.title("🧠 Multi-Graph RAG Command Center")
st.markdown("Direct interface to ChromaDB, Neo4j, and Gemma (Bypassing AnythingLLM)")

# Create our three main UI tabs
tab1, tab2, tab3 = st.tabs(["🗄️ Vector Matrix (Chroma)", "🕸️ Knowledge Graph (Neo4j)", "🤖 Gemma Direct Chat"])
# ==========================================
# TAB 1: CHROMA VECTOR EXPLORER
# ==========================================
with tab1:
    st.header("Vector Matrix Explorer")
    
    @st.cache_resource
    def get_chroma_client():
        return chromadb.HttpClient(host='localhost', port=8000)

    try:
        client = get_chroma_client()
        collections = client.list_collections()
        db_names = [col.name for col in collections]

        if not db_names:
            st.warning("No databases found. The Matrix is empty.")
        else:
            selected_db = st.selectbox("📂 Select Database:", db_names)

            if selected_db:
                collection = client.get_collection(name=selected_db)
                count = collection.count()
                st.success(f"Database '{selected_db}' is online. Total Chunks: {count}")
                
                if count > 0:
                    results = collection.peek(limit=100)
                    
                    # Format into Excel-style DataFrame
                    df = pd.DataFrame({
                        "Chunk ID": results["ids"],
                        "Source": [meta.get('source', 'Unknown') for meta in results["metadatas"]],
                        "Text": results["documents"]
                    })
                    st.dataframe(df, use_container_width=True)
                
                # --- THE DANGER ZONE ---
                st.divider()
                st.subheader("⚠️ Danger Zone")
                with st.expander(f"Delete Database: {selected_db}"):
                    st.error(f"Are you absolutely sure you want to delete **{selected_db}**? This will permanently erase all {count} vectors. This cannot be undone.")
                    
                    # We use type="primary" to make the button red in Streamlit
                    if st.button(f"Yes, Nuke '{selected_db}'", type="primary"):
                        try:
                            client.delete_collection(name=selected_db)
                            st.success(f"💥 '{selected_db}' has been completely wiped from the Matrix!")
                            # Clear the cache and refresh the page instantly so the dropdown updates
                            st.cache_resource.clear()
                            st.rerun()
                        except Exception as e:
                            st.error(f"Failed to delete database: {e}")
                
    except Exception as e:
        st.error(f"Chroma connection failed. Is Docker running? Error: {e}")
# ==========================================
# TAB 2: NEO4J KNOWLEDGE GRAPH
# ==========================================
with tab2:
    st.header("🕸️ Neo4j Direct Query & Schema")
    st.markdown("This sends a request directly to your `server.py` running on Port 5001.")
    
    # --- 1. THE GRAPH SCANNER (Database Overview) ---
    with st.expander("📊 View Graph Schema & Matrix Contents", expanded=False):
        try:
            # Direct connection just for the dashboard stats
            driver = GraphDatabase.driver("bolt://localhost:7687", auth=("neo4j", "password"))
            with driver.session() as session:
                # Query Neo4j for its internal architecture
                labels = session.run("CALL db.labels()").data()
                rel_types = session.run("CALL db.relationshipTypes()").data()
                node_count = session.run("MATCH (n) RETURN count(n) AS c").single()['c']
                rel_count = session.run("MATCH ()-->() RETURN count(*) AS c").single()['c']
                
                st.success(f"Graph is Online! 🟢 Total Nodes: {node_count} | Total Relationships: {rel_count}")
                
                colA, colB = st.columns(2)
                with colA:
                    st.markdown("**Entity Types (Labels):**")
                    for lbl in labels:
                        st.code(lbl['label'])
                with colB:
                    st.markdown("**Connections (Relationships):**")
                    for rel in rel_types:
                        st.code(rel['relationshipType'])
            driver.close()
        except Exception as e:
            st.error(f"Could not scan Neo4j. Is Docker running? Error: {e}")

    # --- 2. PRESET COMMANDS ---
    st.subheader("💡 Quick Commands")
    col1, col2, col3 = st.columns(3)
    preset_q = ""
    
    if col1.button("🍷 Who sold WINE in 2020?"):
        preset_q = "Which supplier sold WINE in 2020 1?"
    if col2.button("📦 What items are there?"):
        preset_q = "List 5 unique items from the database."
    if col3.button("🏭 Find Legends Ltd"):
        preset_q = "What items does LEGENDS LTD supply?"

    # --- 3. THE QUERY INPUT ---
    # Streamlit will automatically fill this input if a button above sets preset_q!
    neo4j_query = st.text_input("Ask the Graph a question:", value=preset_q)
    
    if st.button("Search Graph", type="primary"):
        if neo4j_query:
            with st.spinner("Querying the Graph Matrix..."):
                try:
                    # Hitting the API you already built!
                    response = requests.post(
                        "http://127.0.0.1:5001/ask_neo4j",
                        json={"question": neo4j_query},
                        headers={"Content-Type": "application/json"}
                    )
                    if response.status_code == 200:
                        st.info("Graph Response:")
                        st.write(response.json().get("text", "No text returned."))
                    else:
                        st.error(f"API Error {response.status_code}: {response.text}")
                except requests.exceptions.ConnectionError:
                    st.error("Could not connect to Port 5001. Is `server.py` running?")
# ==========================================
# TAB 3: CUSTOM RAG PIPELINE (THE FINAL BOSS)
# ==========================================
with tab3:
    st.header("🧠 Custom Thesis RAG Agent")
    st.markdown("Direct pipeline: Question -> ChromaDB -> Gemma4 (No AnythingLLM overhead)")
    
    # Select which database to search (defaults to final_thesis if it exists)
    try:
        chroma_client = chromadb.HttpClient(host='localhost', port=8000)
        all_cols = [c.name for c in chroma_client.list_collections()]
        default_idx = all_cols.index("final_thesis") if "final_thesis" in all_cols else 0
        target_db = st.selectbox("🎯 Select Target Database for Context:", all_cols, index=default_idx)
    except Exception:
        st.error("ChromaDB is not running.")
        target_db = None

    # Initialize chat history
    if "rag_messages" not in st.session_state:
        st.session_state.rag_messages = []

    # Display chat history
    for message in st.session_state.rag_messages:
        with st.chat_message(message["role"]):
            st.markdown(message["content"])

    # Chat Input
    if prompt := st.chat_input("Ask a question about your documents..."):
        
        # 1. Show user message
        st.session_state.rag_messages.append({"role": "user", "content": prompt})
        with st.chat_message("user"):
            st.markdown(prompt)

        with st.chat_message("assistant"):
            with st.spinner("Searching the Matrix & Thinking..."):
                try:
                 # STEP 1: RETRIEVE from ChromaDB
                    collection = chroma_client.get_collection(name=target_db)
                    
                    embed_response = requests.post(
                        "http://localhost:11434/api/embeddings",
                        json={"model": "qwen3-embedding:0.6b", "prompt": prompt}
                    )
                    question_vector = embed_response.json().get("embedding")

                    # 1b. Search Chroma (INCREASED TO TOP 10 CHUNKS)
                    search_results = collection.query(
                        query_embeddings=[question_vector],
                        n_results=10 # <--- Grab 10 chunks instead of 5 to cast a wider net!
                    )
                    
                    retrieved_chunks = search_results['documents'][0]
                    retrieved_sources = [meta.get('source', 'Unknown') for meta in search_results['metadatas'][0]]
                    context_block = "\n\n---\n\n".join(retrieved_chunks)

                    # --- NEW X-RAY DEBUGGER ---
                    with st.expander("👀 X-Ray: See exactly what Qwen retrieved for Gemma to read"):
                        st.markdown(f"**Total chunks retrieved:** {len(retrieved_chunks)}")
                        st.text(context_block)

                    # STEP 2: AUGMENT 
                    system_prompt =f"""You are an elite academic assistant. 

First, try to answer the user's question using ONLY the information in the CONTEXT FROM DATABASE below. 

If the exact answer is NOT in the context, you are allowed to use your own general knowledge to answer it. However, if you use your own knowledge, you MUST start your response with: "I couldn't find the exact quote in the retrieved documents, but here is the answer based on my general knowledge:"

CONTEXT FROM DATABASE:
{context_block}

USER QUESTION: 
{prompt}
"""
                    
                    # STEP 3: GENERATE (Send to Ollama)
                    response = requests.post(
                        "http://localhost:11434/api/generate",
                        json={
                            "model": "gemma4:latest",
                            "prompt": system_prompt,
                            "stream": False
                        }
                    )
                    
                    if response.status_code == 200:
                        reply = response.json().get("response", "")
                        
                        # Add a clean UI box showing exactly which PDFs it read
                        unique_sources = list(set(retrieved_sources))
                        source_text = "\n\n**📚 Sources read for this answer:**\n- " + "\n- ".join(unique_sources)
                        
                        final_output = reply + source_text
                        st.markdown(final_output)
                        st.session_state.rag_messages.append({"role": "assistant", "content": final_output})
                    else:
                        st.error(f"Ollama Error: {response.text}")

                except Exception as e:
                    st.error(f"Pipeline Failed: {e}")