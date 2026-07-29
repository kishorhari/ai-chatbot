"""Knowledge application layer — chunking, indexing, and (M3.4+) retrieval.

Pure application use cases and policies over the ``domain/knowledge`` ports
(ADR-0011/0014/0016): the ``ChunkingStrategy`` and the ``IndexingService``
orchestrator now; the ``Retriever`` and ``ContextProvider`` later. Depends only on
domain ports and application collaborators (it reuses the M2 ``TokenEstimator`` and
``Clock``) — never a concrete adapter, embedding SDK, vector client, or framework.
"""
