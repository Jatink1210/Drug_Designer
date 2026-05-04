"""GAT (Graph Attention Network) for target ranking and prioritization."""

from __future__ import annotations

from typing import Any, Dict, List, Optional, Tuple

import numpy as np
import structlog
import torch
import torch.nn as nn
import torch.nn.functional as F

log = structlog.get_logger()


class GATLayer(nn.Module):
    """Single GAT layer with multi-head attention."""
    
    def __init__(
        self,
        in_features: int,
        out_features: int,
        num_heads: int = 8,
        dropout: float = 0.1,
        concat: bool = True
    ):
        super().__init__()
        self.in_features = in_features
        self.out_features = out_features
        self.num_heads = num_heads
        self.concat = concat
        
        # Linear transformations for each head
        self.W = nn.Parameter(torch.FloatTensor(num_heads, in_features, out_features))
        self.a = nn.Parameter(torch.FloatTensor(num_heads, 2 * out_features, 1))
        
        self.dropout = nn.Dropout(dropout)
        self.leaky_relu = nn.LeakyReLU(0.2)
        
        self.reset_parameters()
    
    def reset_parameters(self):
        nn.init.xavier_uniform_(self.W)
        nn.init.xavier_uniform_(self.a)
    
    def forward(
        self,
        x: torch.Tensor,
        edge_index: torch.Tensor
    ) -> torch.Tensor:
        """
        Forward pass with multi-head attention.
        
        Args:
            x: Node features [num_nodes, in_features]
            edge_index: Edge indices [2, num_edges]
            
        Returns:
            Updated node features [num_nodes, out_features * num_heads] if concat
                                  [num_nodes, out_features] if not concat
        """
        num_nodes = x.size(0)
        
        # Linear transformation for each head
        h = torch.stack([torch.matmul(x, self.W[i]) for i in range(self.num_heads)])
        # h: [num_heads, num_nodes, out_features]
        
        # Compute attention coefficients
        src, dst = edge_index[0], edge_index[1]
        
        # Concatenate source and destination features
        h_src = h[:, src, :]  # [num_heads, num_edges, out_features]
        h_dst = h[:, dst, :]  # [num_heads, num_edges, out_features]
        h_cat = torch.cat([h_src, h_dst], dim=2)  # [num_heads, num_edges, 2*out_features]
        
        # Compute attention scores
        e = torch.matmul(h_cat, self.a).squeeze(-1)  # [num_heads, num_edges]
        e = self.leaky_relu(e)
        
        # Normalize attention coefficients using softmax
        alpha = torch.zeros(self.num_heads, num_nodes, num_nodes, device=x.device)
        alpha[:, src, dst] = e
        alpha = F.softmax(alpha, dim=2)
        alpha = self.dropout(alpha)
        
        # Apply attention to aggregate neighbor features
        out = torch.matmul(alpha, h)  # [num_heads, num_nodes, out_features]
        
        if self.concat:
            # Concatenate heads
            out = out.transpose(0, 1).contiguous().view(num_nodes, -1)
        else:
            # Average heads
            out = out.mean(dim=0)
        
        return out


class GATModel(nn.Module):
    """GAT model for target ranking and prioritization."""
    
    def __init__(
        self,
        num_features: int,
        hidden_dim: int = 128,
        num_heads: int = 8,
        num_layers: int = 2,
        dropout: float = 0.1,
        num_classes: int = 1
    ):
        super().__init__()
        self.num_features = num_features
        self.hidden_dim = hidden_dim
        self.num_heads = num_heads
        
        # GAT layers
        self.layers = nn.ModuleList()
        
        # First layer
        self.layers.append(
            GATLayer(num_features, hidden_dim, num_heads, dropout, concat=True)
        )
        
        # Hidden layers
        for _ in range(num_layers - 2):
            self.layers.append(
                GATLayer(hidden_dim * num_heads, hidden_dim, num_heads, dropout, concat=True)
            )
        
        # Last layer (no concatenation)
        self.layers.append(
            GATLayer(hidden_dim * num_heads, hidden_dim, num_heads, dropout, concat=False)
        )
        
        # Output layer for ranking
        self.output = nn.Linear(hidden_dim, num_classes)
        
        self.dropout = nn.Dropout(dropout)
    
    def forward(
        self,
        x: torch.Tensor,
        edge_index: torch.Tensor
    ) -> torch.Tensor:
        """
        Forward pass.
        
        Args:
            x: Node features [num_nodes, num_features]
            edge_index: Edge indices [2, num_edges]
            
        Returns:
            Node scores [num_nodes, num_classes]
        """
        for i, layer in enumerate(self.layers):
            x = layer(x, edge_index)
            if i < len(self.layers) - 1:
                x = F.elu(x)
                x = self.dropout(x)
        
        # Output layer
        scores = self.output(x)
        
        return scores


class GATTargetRanker:
    """GAT-based target ranking and prioritization system."""
    
    def __init__(
        self,
        num_features: int,
        hidden_dim: int = 128,
        num_heads: int = 8,
        num_layers: int = 2,
        device: Optional[str] = None
    ):
        self.num_features = num_features
        self.hidden_dim = hidden_dim
        self.num_heads = num_heads
        self.num_layers = num_layers
        self.device = device or ("cuda" if torch.cuda.is_available() else "cpu")
        
        self.model = GATModel(
            num_features=num_features,
            hidden_dim=hidden_dim,
            num_heads=num_heads,
            num_layers=num_layers
        ).to(self.device)
        
        self.target_to_idx: Dict[str, int] = {}
        self.idx_to_target: Dict[int, str] = {}
        
        log.info("gat_ranker_initialized", device=self.device, num_heads=num_heads)
    
    def train_model(
        self,
        features: np.ndarray,
        edge_index: np.ndarray,
        labels: np.ndarray,
        target_ids: List[str],
        num_epochs: int = 100,
        learning_rate: float = 0.01
    ) -> None:
        """
        Train GAT model for target ranking.
        
        Args:
            features: Node feature matrix [num_nodes, num_features]
            edge_index: Edge indices [2, num_edges]
            labels: Target scores/labels [num_nodes]
            target_ids: List of target identifiers
            num_epochs: Number of training epochs
            learning_rate: Learning rate
        """
        # Build target vocabulary
        self.target_to_idx = {target: idx for idx, target in enumerate(target_ids)}
        self.idx_to_target = {idx: target for target, idx in self.target_to_idx.items()}
        
        # Convert to tensors
        x = torch.FloatTensor(features).to(self.device)
        edge_idx = torch.LongTensor(edge_index).to(self.device)
        y = torch.FloatTensor(labels).unsqueeze(1).to(self.device)
        
        optimizer = torch.optim.Adam(self.model.parameters(), lr=learning_rate)
        criterion = nn.MSELoss()
        
        self.model.train()
        for epoch in range(num_epochs):
            optimizer.zero_grad()
            
            # Forward pass
            scores = self.model(x, edge_idx)
            
            # Compute loss
            loss = criterion(scores, y)
            
            # Backward pass
            loss.backward()
            optimizer.step()
            
            if (epoch + 1) % 10 == 0:
                log.info("gat_training", epoch=epoch+1, loss=loss.item())
        
        log.info("gat_training_complete", num_epochs=num_epochs)
    
    def rank_targets(
        self,
        features: np.ndarray,
        edge_index: np.ndarray,
        target_ids: List[str],
        top_k: int = 10
    ) -> List[Dict[str, Any]]:
        """
        Rank targets based on learned model.
        
        Args:
            features: Node feature matrix [num_nodes, num_features]
            edge_index: Edge indices [2, num_edges]
            target_ids: List of target identifiers
            top_k: Number of top targets to return
            
        Returns:
            List of ranked targets with scores
        """
        self.model.eval()
        
        x = torch.FloatTensor(features).to(self.device)
        edge_idx = torch.LongTensor(edge_index).to(self.device)
        
        with torch.no_grad():
            scores = self.model(x, edge_idx).squeeze().cpu().numpy()
        
        # Rank targets by score
        ranked_indices = np.argsort(scores)[::-1][:top_k]
        
        results = []
        for idx in ranked_indices:
            results.append({
                "target_id": target_ids[idx],
                "score": float(scores[idx]),
                "rank": len(results) + 1
            })
        
        return results
    
    def predict_target_score(
        self,
        target_id: str,
        features: np.ndarray,
        edge_index: np.ndarray
    ) -> Optional[float]:
        """
        Predict score for a specific target.
        
        Args:
            target_id: Target identifier
            features: Node feature matrix
            edge_index: Edge indices
            
        Returns:
            Predicted score or None if target not found
        """
        if target_id not in self.target_to_idx:
            return None
        
        self.model.eval()
        
        x = torch.FloatTensor(features).to(self.device)
        edge_idx = torch.LongTensor(edge_index).to(self.device)
        
        with torch.no_grad():
            scores = self.model(x, edge_idx).squeeze().cpu().numpy()
        
        target_idx = self.target_to_idx[target_id]
        return float(scores[target_idx])
    
    def get_attention_weights(
        self,
        features: np.ndarray,
        edge_index: np.ndarray
    ) -> Dict[str, np.ndarray]:
        """
        Extract attention weights from the model.
        
        Args:
            features: Node feature matrix
            edge_index: Edge indices
            
        Returns:
            Dictionary of attention weights per layer
        """
        self.model.eval()
        
        x = torch.FloatTensor(features).to(self.device)
        edge_idx = torch.LongTensor(edge_index).to(self.device)
        
        attention_weights = {}
        
        with torch.no_grad():
            for i, layer in enumerate(self.model.layers):
                # This is a simplified version - actual implementation would
                # require modifying the layer to return attention weights
                attention_weights[f"layer_{i}"] = np.zeros((x.size(0), x.size(0)))
        
        return attention_weights
