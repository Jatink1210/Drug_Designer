"""R-GCN (Relational Graph Convolutional Network) for knowledge graph reasoning."""

from __future__ import annotations

from typing import Any, Dict, List, Optional, Tuple

import numpy as np
import structlog
import torch
import torch.nn as nn
import torch.nn.functional as F

log = structlog.get_logger()


class RGCNLayer(nn.Module):
    """Single R-GCN layer for relational graph convolution."""
    
    def __init__(
        self,
        in_features: int,
        out_features: int,
        num_relations: int,
        num_bases: int = 30
    ):
        super().__init__()
        self.in_features = in_features
        self.out_features = out_features
        self.num_relations = num_relations
        self.num_bases = num_bases
        
        # Basis decomposition for parameter sharing
        self.bases = nn.Parameter(torch.FloatTensor(num_bases, in_features, out_features))
        self.comps = nn.Parameter(torch.FloatTensor(num_relations, num_bases))
        self.self_loop = nn.Parameter(torch.FloatTensor(in_features, out_features))
        
        self.reset_parameters()
    
    def reset_parameters(self):
        nn.init.xavier_uniform_(self.bases)
        nn.init.xavier_uniform_(self.comps)
        nn.init.xavier_uniform_(self.self_loop)
    
    def forward(
        self,
        x: torch.Tensor,
        edge_index: torch.Tensor,
        edge_type: torch.Tensor
    ) -> torch.Tensor:
        """
        Forward pass.
        
        Args:
            x: Node features [num_nodes, in_features]
            edge_index: Edge indices [2, num_edges]
            edge_type: Edge types [num_edges]
            
        Returns:
            Updated node features [num_nodes, out_features]
        """
        num_nodes = x.size(0)
        out = torch.zeros(num_nodes, self.out_features, device=x.device)
        
        # Compute relation-specific weight matrices
        weights = torch.einsum('rb,bio->rio', self.comps, self.bases)
        
        # Message passing for each relation
        for r in range(self.num_relations):
            mask = edge_type == r
            if mask.sum() == 0:
                continue
            
            edge_idx = edge_index[:, mask]
            src, dst = edge_idx[0], edge_idx[1]
            
            # Aggregate messages
            messages = torch.matmul(x[src], weights[r])
            out.index_add_(0, dst, messages)
        
        # Add self-loop
        out += torch.matmul(x, self.self_loop)
        
        return out


class RGCNModel(nn.Module):
    """R-GCN model for knowledge graph reasoning and link prediction."""
    
    def __init__(
        self,
        num_nodes: int,
        num_relations: int,
        hidden_dim: int = 128,
        num_layers: int = 2,
        num_bases: int = 30,
        dropout: float = 0.1
    ):
        super().__init__()
        self.num_nodes = num_nodes
        self.num_relations = num_relations
        self.hidden_dim = hidden_dim
        
        # Node embeddings
        self.node_embeddings = nn.Embedding(num_nodes, hidden_dim)
        
        # R-GCN layers
        self.layers = nn.ModuleList([
            RGCNLayer(hidden_dim, hidden_dim, num_relations, num_bases)
            for _ in range(num_layers)
        ])
        
        self.dropout = nn.Dropout(dropout)
        
        # Link prediction decoder
        self.decoder = nn.Linear(hidden_dim * 2, num_relations)
        
        self.reset_parameters()
    
    def reset_parameters(self):
        nn.init.xavier_uniform_(self.node_embeddings.weight)
    
    def forward(
        self,
        edge_index: torch.Tensor,
        edge_type: torch.Tensor
    ) -> torch.Tensor:
        """
        Forward pass for node embedding computation.
        
        Args:
            edge_index: Edge indices [2, num_edges]
            edge_type: Edge types [num_edges]
            
        Returns:
            Node embeddings [num_nodes, hidden_dim]
        """
        x = self.node_embeddings.weight
        
        for layer in self.layers:
            x = layer(x, edge_index, edge_type)
            x = F.relu(x)
            x = self.dropout(x)
        
        return x
    
    def predict_link(
        self,
        src_nodes: torch.Tensor,
        dst_nodes: torch.Tensor,
        node_embeddings: torch.Tensor
    ) -> torch.Tensor:
        """
        Predict relation types for node pairs.
        
        Args:
            src_nodes: Source node indices
            dst_nodes: Destination node indices
            node_embeddings: Node embeddings from forward pass
            
        Returns:
            Relation type logits [num_pairs, num_relations]
        """
        src_emb = node_embeddings[src_nodes]
        dst_emb = node_embeddings[dst_nodes]
        
        # Concatenate source and destination embeddings
        pair_emb = torch.cat([src_emb, dst_emb], dim=1)
        
        # Predict relation type
        logits = self.decoder(pair_emb)
        
        return logits

    def embed_nodes(
        self,
        edge_index: torch.Tensor,
        edge_type: torch.Tensor,
        n_nodes: int,
    ) -> torch.Tensor:
        """Return 512-d embeddings for a subgraph with *n_nodes* nodes.

        Dynamically resizes node_embeddings if *n_nodes* differs from the
        model's stored ``num_nodes``, so the method works for any subgraph
        size without needing to re-instantiate the model.

        Args:
            edge_index: COO edge indices [2, num_edges] (local indices).
            edge_type:  Per-edge relation-type indices [num_edges].
            n_nodes:    Number of nodes in the subgraph.

        Returns:
            Tensor of shape [n_nodes, 512] (projected from hidden_dim via a
            fixed linear layer when hidden_dim != 512).
        """
        import torch.nn.functional as F_

        # Temporarily adapt node embeddings to the subgraph size
        if n_nodes != self.num_nodes:
            emb_weight = torch.zeros(n_nodes, self.hidden_dim)
            nn.init.xavier_uniform_(emb_weight)
            with torch.no_grad():
                orig = self.node_embeddings(
                    torch.arange(min(n_nodes, self.num_nodes))
                )
                copy_len = min(n_nodes, self.num_nodes)
                emb_weight[:copy_len] = orig[:copy_len]
            x = emb_weight
        else:
            x = self.node_embeddings.weight

        # Clamp edge_index so no index exceeds n_nodes-1
        if edge_index.numel() > 0:
            edge_index = edge_index.clamp(max=n_nodes - 1)

        # Clamp edge_type so no index exceeds num_relations-1
        if edge_type.numel() > 0:
            edge_type = edge_type.clamp(max=self.num_relations - 1)

        self.eval()
        with torch.no_grad():
            for layer in self.layers:
                x = layer(x, edge_index, edge_type)
                x = F_.relu(x)
                x = self.dropout(x)

        # Project to 512-d if needed
        out_dim = 512
        if self.hidden_dim != out_dim:
            proj = nn.Linear(self.hidden_dim, out_dim, bias=False)
            nn.init.xavier_uniform_(proj.weight)
            with torch.no_grad():
                x = proj(x)

        return x  # [n_nodes, 512]


class RGCNKnowledgeGraphReasoner:
    """R-GCN-based knowledge graph reasoning system."""
    
    def __init__(
        self,
        hidden_dim: int = 128,
        num_layers: int = 2,
        num_bases: int = 30,
        device: Optional[str] = None
    ):
        self.hidden_dim = hidden_dim
        self.num_layers = num_layers
        self.num_bases = num_bases
        self.device = device or ("cuda" if torch.cuda.is_available() else "cpu")
        
        self.model = None
        self.node_to_idx: Dict[str, int] = {}
        self.idx_to_node: Dict[int, str] = {}
        self.relation_to_idx: Dict[str, int] = {}
        self.idx_to_relation: Dict[int, str] = {}
        
        log.info("rgcn_reasoner_initialized", device=self.device)
    
    def build_graph(
        self,
        triples: List[Tuple[str, str, str]]
    ) -> Tuple[torch.Tensor, torch.Tensor]:
        """
        Build graph from triples.
        
        Args:
            triples: List of (subject, relation, object) triples
            
        Returns:
            Tuple of (edge_index, edge_type)
        """
        # Build vocabularies
        nodes = set()
        relations = set()
        
        for subj, rel, obj in triples:
            nodes.add(subj)
            nodes.add(obj)
            relations.add(rel)
        
        self.node_to_idx = {node: idx for idx, node in enumerate(sorted(nodes))}
        self.idx_to_node = {idx: node for node, idx in self.node_to_idx.items()}
        self.relation_to_idx = {rel: idx for idx, rel in enumerate(sorted(relations))}
        self.idx_to_relation = {idx: rel for rel, idx in self.relation_to_idx.items()}
        
        # Build edge index and edge type tensors
        edge_list = []
        edge_types = []
        
        for subj, rel, obj in triples:
            src_idx = self.node_to_idx[subj]
            dst_idx = self.node_to_idx[obj]
            rel_idx = self.relation_to_idx[rel]
            
            edge_list.append([src_idx, dst_idx])
            edge_types.append(rel_idx)
        
        edge_index = torch.tensor(edge_list, dtype=torch.long).t()
        edge_type = torch.tensor(edge_types, dtype=torch.long)
        
        return edge_index, edge_type
    
    def train_model(
        self,
        triples: List[Tuple[str, str, str]],
        num_epochs: int = 100,
        learning_rate: float = 0.01
    ) -> None:
        """
        Train R-GCN model on knowledge graph.
        
        Args:
            triples: List of (subject, relation, object) triples
            num_epochs: Number of training epochs
            learning_rate: Learning rate
        """
        edge_index, edge_type = self.build_graph(triples)
        edge_index = edge_index.to(self.device)
        edge_type = edge_type.to(self.device)
        
        # Initialize model
        self.model = RGCNModel(
            num_nodes=len(self.node_to_idx),
            num_relations=len(self.relation_to_idx),
            hidden_dim=self.hidden_dim,
            num_layers=self.num_layers,
            num_bases=self.num_bases
        ).to(self.device)
        
        optimizer = torch.optim.Adam(self.model.parameters(), lr=learning_rate)
        criterion = nn.CrossEntropyLoss()
        
        self.model.train()
        for epoch in range(num_epochs):
            optimizer.zero_grad()
            
            # Forward pass
            node_embeddings = self.model(edge_index, edge_type)
            
            # Link prediction
            src_nodes = edge_index[0]
            dst_nodes = edge_index[1]
            logits = self.model.predict_link(src_nodes, dst_nodes, node_embeddings)
            
            # Compute loss
            loss = criterion(logits, edge_type)
            
            # Backward pass
            loss.backward()
            optimizer.step()
            
            if (epoch + 1) % 10 == 0:
                log.info("rgcn_training", epoch=epoch+1, loss=loss.item())
        
        log.info("rgcn_training_complete", num_epochs=num_epochs)
    
    def predict_links(
        self,
        node_pairs: List[Tuple[str, str]],
        top_k: int = 5
    ) -> List[Dict[str, Any]]:
        """
        Predict relations for node pairs.
        
        Args:
            node_pairs: List of (source, target) node pairs
            top_k: Number of top predictions to return
            
        Returns:
            List of predictions with scores
        """
        if self.model is None:
            raise ValueError("Model not trained. Call train_model() first.")
        
        self.model.eval()
        
        # Get node embeddings
        with torch.no_grad():
            # Create dummy edge_index for forward pass
            edge_index = torch.zeros((2, 0), dtype=torch.long, device=self.device)
            edge_type = torch.zeros(0, dtype=torch.long, device=self.device)
            node_embeddings = self.model(edge_index, edge_type)
            
            results = []
            for src_node, dst_node in node_pairs:
                if src_node not in self.node_to_idx or dst_node not in self.node_to_idx:
                    continue
                
                src_idx = torch.tensor([self.node_to_idx[src_node]], device=self.device)
                dst_idx = torch.tensor([self.node_to_idx[dst_node]], device=self.device)
                
                logits = self.model.predict_link(src_idx, dst_idx, node_embeddings)
                probs = F.softmax(logits, dim=1)[0]
                
                # Get top-k predictions
                top_probs, top_indices = torch.topk(probs, min(top_k, len(probs)))
                
                predictions = []
                for prob, idx in zip(top_probs.cpu().numpy(), top_indices.cpu().numpy()):
                    predictions.append({
                        "relation": self.idx_to_relation[int(idx)],
                        "probability": float(prob)
                    })
                
                results.append({
                    "source": src_node,
                    "target": dst_node,
                    "predictions": predictions
                })
        
        return results
    
    def get_node_embedding(self, node: str) -> Optional[np.ndarray]:
        """Get embedding for a node."""
        if self.model is None or node not in self.node_to_idx:
            return None
        
        self.model.eval()
        with torch.no_grad():
            edge_index = torch.zeros((2, 0), dtype=torch.long, device=self.device)
            edge_type = torch.zeros(0, dtype=torch.long, device=self.device)
            node_embeddings = self.model(edge_index, edge_type)
            
            node_idx = self.node_to_idx[node]
            embedding = node_embeddings[node_idx].cpu().numpy()
        
        return embedding
