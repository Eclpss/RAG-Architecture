<p align="center">
  <img src="https://raw.githubusercontent.com/safishamsi/graphify/v4/docs/logo-text.svg" width="260" height="64" alt="Graphify"/>
</p>

# 🚀 Multi-Agent Dual-Brain RAG Architecture

This repository houses a customized, enterprise-grade Retrieval-Augmented Generation (RAG) architecture. It utilizes a dual-database approach (Knowledge Graph + Vector Matrix) orchestrated by n8n, powered by local LLMs via Ollama, and seamlessly bridged by a custom Python extraction engine.

---

## 🏗️ System Architecture Overview
* **Orchestration:** n8n
* **Knowledge Graph:** Neo4j (Entity & Relationship Mapping)
* **Vector Database:** ChromaDB (Semantic Text Chunks)
* **Local AI Engine:** Ollama (Hosting specialized agents)
* **Frontend UI:** AnythingLLM Desktop
* **Extraction Server:** Custom Python natively bridging Docker and the Host OS.

---

## ⚙️ Phase 1: Core Infrastructure (Docker)

The foundational databases and orchestration engine are containerized for stability. Ensure **Docker Desktop for Windows** is installed and running before executing these commands.

### 1. Install Neo4j (Knowledge Graph)
Neo4j handles the entity relationships. We expose ports `7474` for the browser UI and `7687` for the Python connection. Open your Command Prompt (`cmd`) and run:
```bash
docker run -d --name neo4j -p 7474:7474 -p 7687:7687 --env NEO4J_AUTH=neo4j/password -v neo4j_data:/data neo4j:latest
