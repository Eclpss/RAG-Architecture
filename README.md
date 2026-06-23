<p align="center">
  <img src="https://raw.githubusercontent.com/safishamsi/graphify/v4/docs/logo-text.svg" width="260" height="64" alt="Graphify"/>
</p>

# 🚀 Multi-Agent Dual-Brain RAG Architecture

This repository houses a customized, enterprise-grade Retrieval-Augmented Generation (RAG) architecture. It utilizes a dual-database approach (Knowledge Graph + Vector Matrix) orchestrated by n8n, powered by local LLMs via Ollama, and seamlessly bridged by a custom Python extraction engine.

> ⚠️ **MUST DO:** Follow the full documentation in the Google Doc below first. Once you reach **Phase 5** in that doc, come back to this repo to continue with the next steps.

📄 **[Full Documentation (Google Docs)](https://docs.google.com/document/d/1PasmrAv3nz3n6Tco07IjREQD14dBG3VJbSPN5xgujAk/edit?usp=sharing)**

---

## 🏗️ System Architecture Overview

* **Orchestration:** n8n
* **Knowledge Graph:** Neo4j (Entity & Relationship Mapping)
* **Vector Database:** ChromaDB (Semantic Text Chunks)
* **Local AI Engine:** Ollama (Hosting specialized agents)
* **Frontend UI:** AnythingLLM Desktop
* **Extraction Server:** Custom Python natively bridging Docker and the Host OS

---

## 🐍 Phase 3: The Python Extraction Engine

The custom Python scripts act as the bridge, processing files natively on Windows and pushing them into the Dockerized databases.

### 1. Setup the Environment

Extract the repository folder to your local machine. Open your terminal inside the project folder and install all necessary dependencies using the provided requirements file:

```bash
python -m venv .venv
.venv\Scripts\activate.bat
:: On Git Bash / Linux / Mac, use: source .venv/Scripts/activate (or .venv/bin/activate)
pip install -r requirements.txt
```

### 2. Booting the Servers

This architecture utilizes a dual-script setup to handle different parts of the pipeline. You will need to run both of these scripts in **separate terminal windows**.

**Run the Vector Processing Server (`server.py`):** This script is specifically designed to handle the n8n Form Node. It receives document submissions, chunks the data, and embeds it directly into ChromaDB.

```bash
python server.py
```

**Run the Graph Processing Server (`app.py`):** This script is strictly dedicated to Neo4j. It handles the complex Multi-Agent logic, extracting semantic entities from the text and drawing the relationships inside the Knowledge Graph.

```bash
python app.py
```

---

## 🖥️ Phase 4: User Interface (AnythingLLM)

AnythingLLM serves as the unified chat interface to query the dual-brain architecture.

1. Download and install **AnythingLLM Desktop** from [anythingllm.com](https://anythingllm.com).
2. **Connect the AI Engine:** Go to `Settings ⚙️ → LLM Provider → Select Ollama`. Set the URL to `http://127.0.0.1:11434` and select your preferred conversational model.
3. **Connect the Memory:** Go to `Settings ⚙️ → Vector Database → Select Chroma`. Set the URL to `http://127.0.0.1:8000`.
