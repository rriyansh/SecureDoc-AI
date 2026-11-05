# SecureDoc AI: Guardrailed Enterprise RAG Infrastructure

## System Overview
SecureDoc AI is a Retrieval-Augmented Generation (RAG) pipeline designed for enterprise environments where data leakage and model hallucination are unacceptable. The system moves beyond naive fixed-size token splitting by implementing semantic boundary chunking and enforces strict input/output validation using NeMo Guardrails.

## Architecture & Data Flow
1. **Ingestion & Processing:** Documents are processed using semantic chunking to preserve contextual integrity. Vector embeddings are generated and stored in a Qdrant vector database utilizing an HNSW index for sub-millisecond retrieval.
2. **Hybrid Retrieval:** The retrieval pipeline executes a dense vector search (Qdrant) in parallel with lexical keyword search (BM25). A cross-encoder model re-ranks the combined candidate pool to optimize context precision.
3. **Security Layer:** NVIDIA NeMo Guardrails intercepts all queries to prevent prompt injection and topical deviation. Post-generation, the output is screened for hallucinations against the retrieved context.
4. **Continuous Evaluation:** The pipeline is integrated with the RAGAS framework to continuously monitor retrieval recall and generation faithfulness.

## Engineering Trade-offs & Optimizations
- **Latency vs. Precision:** Cross-encoder re-ranking introduces a ~150ms latency penalty. This was mitigated by restricting the re-ranking candidate pool to the top 25 documents from the initial hybrid retrieval phase.
- **Guardrail Overhead:** NeMo Guardrails requires additional LLM calls for topical alignment. We optimized this by deploying a smaller, quantized model (Llama-3 8B) specifically for the routing and guardrail classification tasks.

## Tech Stack
- **Frameworks:** LlamaIndex, LangChain, FastAPI
- **Infrastructure:** Qdrant, Docker
- **Evaluation & Security:** NVIDIA NeMo Guardrails, RAGAS

## Performance Metrics
- **Context Precision:** 88.4% (measured via RAGAS)
- **Faithfulness Score:** >0.92 on benchmark enterprise datasets.
- **P95 Latency:** <800ms end-to-end response time.
