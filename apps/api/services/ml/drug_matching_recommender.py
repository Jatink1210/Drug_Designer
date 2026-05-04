"""AI drug matching recommender for targeted therapy selection."""

from __future__ import annotations

from typing import Any, Dict, List, Optional, Tuple

import numpy as np
import structlog
from sklearn.metrics.pairwise import cosine_similarity

log = structlog.get_logger()


class DrugMatchingRecommender:
    """
    AI-powered drug matching recommender system.
    
    Uses collaborative filtering and content-based approaches to recommend
    drugs based on pathway disruptions, molecular targets, and mechanism of action.
    """
    
    def __init__(
        self,
        similarity_threshold: float = 0.7,
        top_k: int = 10
    ):
        """
        Initialize drug matching recommender.
        
        Args:
            similarity_threshold: Minimum similarity for recommendations
            top_k: Number of top recommendations to return
        """
        self.similarity_threshold = similarity_threshold
        self.top_k = top_k
        
        # Drug-pathway interaction matrix
        self.drug_pathway_matrix: Optional[np.ndarray] = None
        self.drug_ids: List[str] = []
        self.pathway_ids: List[str] = []
        
        # Drug features
        self.drug_features: Dict[str, Dict[str, Any]] = {}
        
        log.info("drug_recommender_initialized", threshold=similarity_threshold)
    
    def build_interaction_matrix(
        self,
        drug_pathway_interactions: List[Tuple[str, str, float]]
    ) -> None:
        """
        Build drug-pathway interaction matrix.
        
        Args:
            drug_pathway_interactions: List of (drug_id, pathway_id, interaction_score) tuples
        """
        # Extract unique drugs and pathways
        drugs = sorted(set(drug for drug, _, _ in drug_pathway_interactions))
        pathways = sorted(set(pathway for _, pathway, _ in drug_pathway_interactions))
        
        self.drug_ids = drugs
        self.pathway_ids = pathways
        
        # Build interaction matrix
        drug_idx = {drug: i for i, drug in enumerate(drugs)}
        pathway_idx = {pathway: i for i, pathway in enumerate(pathways)}
        
        matrix = np.zeros((len(drugs), len(pathways)))
        
        for drug, pathway, score in drug_pathway_interactions:
            i = drug_idx[drug]
            j = pathway_idx[pathway]
            matrix[i, j] = score
        
        self.drug_pathway_matrix = matrix
        
        log.info("interaction_matrix_built", num_drugs=len(drugs), num_pathways=len(pathways))
    
    def add_drug_features(
        self,
        drug_id: str,
        features: Dict[str, Any]
    ) -> None:
        """
        Add features for a drug.
        
        Args:
            drug_id: Drug identifier
            features: Drug features (mechanism, targets, properties, etc.)
        """
        self.drug_features[drug_id] = features
    
    def recommend_drugs_for_pathways(
        self,
        disrupted_pathways: List[str],
        pathway_scores: Optional[Dict[str, float]] = None
    ) -> List[Dict[str, Any]]:
        """
        Recommend drugs that target disrupted pathways.
        
        Args:
            disrupted_pathways: List of disrupted pathway IDs
            pathway_scores: Optional disruption scores for each pathway
            
        Returns:
            List of drug recommendations with scores
        """
        if self.drug_pathway_matrix is None:
            raise ValueError("Interaction matrix not built. Call build_interaction_matrix() first.")
        
        # Create query vector
        query_vector = np.zeros(len(self.pathway_ids))
        
        for pathway in disrupted_pathways:
            if pathway in self.pathway_ids:
                idx = self.pathway_ids.index(pathway)
                score = pathway_scores.get(pathway, 1.0) if pathway_scores else 1.0
                query_vector[idx] = score
        
        # Compute similarity scores
        similarities = cosine_similarity(
            query_vector.reshape(1, -1),
            self.drug_pathway_matrix
        )[0]
        
        # Rank drugs
        ranked_indices = np.argsort(similarities)[::-1]
        
        recommendations = []
        for idx in ranked_indices[:self.top_k]:
            if similarities[idx] >= self.similarity_threshold:
                drug_id = self.drug_ids[idx]
                
                # Get drug features
                features = self.drug_features.get(drug_id, {})
                
                recommendations.append({
                    "drug_id": drug_id,
                    "drug_name": features.get("name", drug_id),
                    "relevance_score": float(similarities[idx]),
                    "mechanism_of_action": features.get("mechanism", ""),
                    "targets": features.get("targets", []),
                    "clinical_phase": features.get("clinical_phase", ""),
                    "safety_profile": features.get("safety_profile", {}),
                    "matched_pathways": self._get_matched_pathways(idx, disrupted_pathways)
                })
        
        log.info("drug_recommendations_generated", num_recommendations=len(recommendations))
        return recommendations
    
    def _get_matched_pathways(
        self,
        drug_idx: int,
        query_pathways: List[str]
    ) -> List[Dict[str, Any]]:
        """Get pathways matched by a drug."""
        matched = []
        
        for pathway in query_pathways:
            if pathway in self.pathway_ids:
                pathway_idx = self.pathway_ids.index(pathway)
                interaction_score = self.drug_pathway_matrix[drug_idx, pathway_idx]
                
                if interaction_score > 0:
                    matched.append({
                        "pathway_id": pathway,
                        "interaction_score": float(interaction_score)
                    })
        
        return matched
    
    def recommend_drugs_for_targets(
        self,
        target_proteins: List[str],
        target_scores: Optional[Dict[str, float]] = None
    ) -> List[Dict[str, Any]]:
        """
        Recommend drugs based on target proteins.
        
        Args:
            target_proteins: List of target protein IDs
            target_scores: Optional importance scores for each target
            
        Returns:
            List of drug recommendations
        """
        recommendations = []
        
        for drug_id, features in self.drug_features.items():
            drug_targets = features.get("targets", [])
            
            # Compute overlap with query targets
            matched_targets = set(drug_targets) & set(target_proteins)
            
            if matched_targets:
                # Compute relevance score
                overlap_score = len(matched_targets) / len(target_proteins)
                
                # Weight by target scores if provided
                if target_scores:
                    weighted_score = sum(
                        target_scores.get(target, 1.0)
                        for target in matched_targets
                    ) / len(target_proteins)
                else:
                    weighted_score = overlap_score
                
                if weighted_score >= self.similarity_threshold:
                    recommendations.append({
                        "drug_id": drug_id,
                        "drug_name": features.get("name", drug_id),
                        "relevance_score": float(weighted_score),
                        "mechanism_of_action": features.get("mechanism", ""),
                        "matched_targets": list(matched_targets),
                        "num_matched_targets": len(matched_targets),
                        "clinical_phase": features.get("clinical_phase", ""),
                        "safety_profile": features.get("safety_profile", {})
                    })
        
        # Sort by relevance score
        recommendations.sort(key=lambda x: x["relevance_score"], reverse=True)
        
        return recommendations[:self.top_k]
    
    def recommend_drugs_hybrid(
        self,
        disrupted_pathways: List[str],
        target_proteins: List[str],
        pathway_scores: Optional[Dict[str, float]] = None,
        target_scores: Optional[Dict[str, float]] = None,
        pathway_weight: float = 0.6,
        target_weight: float = 0.4
    ) -> List[Dict[str, Any]]:
        """
        Hybrid recommendation combining pathway and target-based approaches.
        
        Args:
            disrupted_pathways: List of disrupted pathways
            target_proteins: List of target proteins
            pathway_scores: Optional pathway disruption scores
            target_scores: Optional target importance scores
            pathway_weight: Weight for pathway-based score
            target_weight: Weight for target-based score
            
        Returns:
            List of drug recommendations
        """
        # Get pathway-based recommendations
        pathway_recs = self.recommend_drugs_for_pathways(
            disrupted_pathways, pathway_scores
        )
        
        # Get target-based recommendations
        target_recs = self.recommend_drugs_for_targets(
            target_proteins, target_scores
        )
        
        # Combine recommendations
        combined_scores: Dict[str, Dict[str, Any]] = {}
        
        for rec in pathway_recs:
            drug_id = rec["drug_id"]
            combined_scores[drug_id] = {
                "drug_id": drug_id,
                "drug_name": rec["drug_name"],
                "pathway_score": rec["relevance_score"],
                "target_score": 0.0,
                "mechanism_of_action": rec["mechanism_of_action"],
                "clinical_phase": rec["clinical_phase"],
                "safety_profile": rec["safety_profile"],
                "matched_pathways": rec.get("matched_pathways", []),
                "matched_targets": []
            }
        
        for rec in target_recs:
            drug_id = rec["drug_id"]
            if drug_id in combined_scores:
                combined_scores[drug_id]["target_score"] = rec["relevance_score"]
                combined_scores[drug_id]["matched_targets"] = rec.get("matched_targets", [])
            else:
                combined_scores[drug_id] = {
                    "drug_id": drug_id,
                    "drug_name": rec["drug_name"],
                    "pathway_score": 0.0,
                    "target_score": rec["relevance_score"],
                    "mechanism_of_action": rec["mechanism_of_action"],
                    "clinical_phase": rec["clinical_phase"],
                    "safety_profile": rec["safety_profile"],
                    "matched_pathways": [],
                    "matched_targets": rec.get("matched_targets", [])
                }
        
        # Compute combined scores
        recommendations = []
        for drug_id, scores in combined_scores.items():
            combined_score = (
                pathway_weight * scores["pathway_score"] +
                target_weight * scores["target_score"]
            )
            
            recommendations.append({
                **scores,
                "combined_relevance_score": float(combined_score),
                "pathway_contribution": float(pathway_weight * scores["pathway_score"]),
                "target_contribution": float(target_weight * scores["target_score"])
            })
        
        # Sort by combined score
        recommendations.sort(key=lambda x: x["combined_relevance_score"], reverse=True)
        
        return recommendations[:self.top_k]
    
    def explain_recommendation(
        self,
        drug_id: str,
        disrupted_pathways: List[str],
        target_proteins: List[str]
    ) -> Dict[str, Any]:
        """
        Provide detailed explanation for a drug recommendation.
        
        Args:
            drug_id: Drug identifier
            disrupted_pathways: Disrupted pathways
            target_proteins: Target proteins
            
        Returns:
            Detailed explanation of recommendation
        """
        features = self.drug_features.get(drug_id, {})
        
        # Find matched pathways
        matched_pathways = []
        if self.drug_pathway_matrix is not None and drug_id in self.drug_ids:
            drug_idx = self.drug_ids.index(drug_id)
            matched_pathways = self._get_matched_pathways(drug_idx, disrupted_pathways)
        
        # Find matched targets
        drug_targets = features.get("targets", [])
        matched_targets = list(set(drug_targets) & set(target_proteins))
        
        return {
            "drug_id": drug_id,
            "drug_name": features.get("name", drug_id),
            "mechanism_of_action": features.get("mechanism", ""),
            "matched_pathways": matched_pathways,
            "matched_targets": matched_targets,
            "pathway_coverage": len(matched_pathways) / len(disrupted_pathways) if disrupted_pathways else 0,
            "target_coverage": len(matched_targets) / len(target_proteins) if target_proteins else 0,
            "clinical_phase": features.get("clinical_phase", ""),
            "safety_profile": features.get("safety_profile", {}),
            "explanation": self._generate_explanation_text(
                features, matched_pathways, matched_targets
            )
        }
    
    def _generate_explanation_text(
        self,
        features: Dict[str, Any],
        matched_pathways: List[Dict[str, Any]],
        matched_targets: List[str]
    ) -> str:
        """Generate human-readable explanation."""
        drug_name = features.get("name", "This drug")
        mechanism = features.get("mechanism", "unknown mechanism")
        
        explanation = f"{drug_name} works through {mechanism}. "
        
        if matched_pathways:
            explanation += f"It targets {len(matched_pathways)} of the disrupted pathways. "
        
        if matched_targets:
            explanation += f"It acts on {len(matched_targets)} relevant protein targets. "
        
        return explanation
