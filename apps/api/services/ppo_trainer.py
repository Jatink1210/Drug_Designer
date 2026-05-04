"""PPO (Proximal Policy Optimization) Training Loop for Molecule Design (§84).

Implements:
- Rollout buffer with GAE (Generalized Advantage Estimation)
- Clipped surrogate objective
- Multiple epochs per batch
- Value function loss + entropy bonus
- Integration with MoleculeGNNPolicy from dl_models.py
"""
from __future__ import annotations

import logging
import math
from typing import Any, Dict, List, Optional, Tuple

import structlog

log = structlog.get_logger(__name__)

try:
    import torch
    import torch.nn as nn
    import torch.nn.functional as F
    import numpy as np
    TORCH_AVAILABLE = True
except ImportError:
    TORCH_AVAILABLE = False


# ── Rollout Buffer ─────────────────────────────────────────

class RolloutBuffer:
    """Stores rollout trajectories for PPO updates (§84.3).

    Each entry: (state, action, log_prob, reward, value, done)
    Computes GAE advantages on demand.
    """

    def __init__(self, gamma: float = 0.99, gae_lambda: float = 0.95):
        self.gamma = gamma
        self.gae_lambda = gae_lambda
        self.states: list = []
        self.actions: list = []
        self.log_probs: list = []
        self.rewards: list = []
        self.values: list = []
        self.dones: list = []

    def store(self, state, action: int, log_prob: float,
              reward: float, value: float, done: bool):
        self.states.append(state)
        self.actions.append(action)
        self.log_probs.append(log_prob)
        self.rewards.append(reward)
        self.values.append(value)
        self.dones.append(done)

    def clear(self):
        self.states.clear()
        self.actions.clear()
        self.log_probs.clear()
        self.rewards.clear()
        self.values.clear()
        self.dones.clear()

    def __len__(self):
        return len(self.rewards)

    def compute_gae(self, last_value: float = 0.0) -> Tuple:
        """Compute Generalized Advantage Estimation (§84.3).

        A_t = δ_t + (γλ)δ_{t+1} + (γλ)²δ_{t+2} + ...
        where δ_t = r_t + γV(s_{t+1}) - V(s_t)

        Returns (advantages, returns) as tensors.
        """
        if not TORCH_AVAILABLE:
            raise RuntimeError("PyTorch required for PPO training")

        n = len(self.rewards)
        advantages = torch.zeros(n)
        returns = torch.zeros(n)

        gae = 0.0
        next_value = last_value

        for t in reversed(range(n)):
            mask = 1.0 - float(self.dones[t])
            delta = self.rewards[t] + self.gamma * next_value * mask - self.values[t]
            gae = delta + self.gamma * self.gae_lambda * mask * gae
            advantages[t] = gae
            returns[t] = gae + self.values[t]
            next_value = self.values[t]

        return advantages, returns


# ── PPO Trainer ────────────────────────────────────────────

class PPOTrainer:
    """Proximal Policy Optimization for molecule design (§84).

    Rollout loop:
      1. Generate molecule (sample action from policy)
      2. Score via ADMET + docking → compute reward
      3. Store transition in rollout buffer
      4. When buffer full → compute GAE → run K epochs of clipped PPO update

    Parameters:
      clip_epsilon: PPO clipping parameter (default 0.2)
      vf_coeff: Value function loss coefficient (default 0.5)
      ent_coeff: Entropy bonus coefficient (default 0.01)
      max_grad_norm: Gradient clipping norm (default 0.5)
      epochs_per_batch: Number of optimization epochs per rollout batch (default 4)
      batch_size: Mini-batch size for updates (default 64)
      rollout_steps: Steps per rollout before update (default 256)
    """

    def __init__(
        self,
        policy: Any,
        lr: float = 3e-4,
        clip_epsilon: float = 0.2,
        vf_coeff: float = 0.5,
        ent_coeff: float = 0.01,
        gamma: float = 0.99,
        gae_lambda: float = 0.95,
        max_grad_norm: float = 0.5,
        epochs_per_batch: int = 4,
        batch_size: int = 64,
        rollout_steps: int = 256,
    ):
        if not TORCH_AVAILABLE:
            raise RuntimeError("PyTorch required for PPO training")

        self.policy = policy
        self.optimizer = torch.optim.Adam(policy.parameters(), lr=lr)
        self.clip_epsilon = clip_epsilon
        self.vf_coeff = vf_coeff
        self.ent_coeff = ent_coeff
        self.max_grad_norm = max_grad_norm
        self.epochs_per_batch = epochs_per_batch
        self.batch_size = batch_size
        self.rollout_steps = rollout_steps
        self.buffer = RolloutBuffer(gamma=gamma, gae_lambda=gae_lambda)

    def select_action(self, state: Any) -> Tuple[int, float, float]:
        """Sample action from the policy, return (action, log_prob, value)."""
        with torch.no_grad():
            action_logits, value = self.policy(state)
            dist = torch.distributions.Categorical(logits=action_logits.squeeze(0))
            action = dist.sample()
            log_prob = dist.log_prob(action)
        return action.item(), log_prob.item(), value.squeeze().item()

    def compute_loss(
        self,
        states: torch.Tensor,
        actions: torch.Tensor,
        old_log_probs: torch.Tensor,
        advantages: torch.Tensor,
        returns: torch.Tensor,
    ) -> Tuple[torch.Tensor, Dict[str, float]]:
        """Compute clipped PPO surrogate objective + value loss + entropy bonus.

        L = L_clip - c1 * L_vf + c2 * H[π]

        where:
          L_clip = min(r_t * A_t, clip(r_t, 1-ε, 1+ε) * A_t)
          L_vf   = MSE(V(s_t), R_t)
          H[π]   = -Σ π(a|s) log π(a|s)
        """
        action_logits, values = self.policy(states)
        values = values.squeeze(-1)

        dist = torch.distributions.Categorical(logits=action_logits)
        new_log_probs = dist.log_prob(actions)
        entropy = dist.entropy().mean()

        # Ratio r_t = π_new(a|s) / π_old(a|s)
        ratio = (new_log_probs - old_log_probs).exp()

        # Clipped surrogate objective
        surr1 = ratio * advantages
        surr2 = torch.clamp(ratio, 1.0 - self.clip_epsilon, 1.0 + self.clip_epsilon) * advantages
        policy_loss = -torch.min(surr1, surr2).mean()

        # Value function loss
        value_loss = F.mse_loss(values, returns)

        # Total loss
        loss = policy_loss + self.vf_coeff * value_loss - self.ent_coeff * entropy

        metrics = {
            "policy_loss": policy_loss.item(),
            "value_loss": value_loss.item(),
            "entropy": entropy.item(),
            "total_loss": loss.item(),
            "approx_kl": ((ratio - 1) - (ratio.log())).mean().item(),
            "clip_fraction": ((ratio - 1.0).abs() > self.clip_epsilon).float().mean().item(),
        }

        return loss, metrics

    def update(self) -> Dict[str, float]:
        """Run K epochs of PPO updates on the current rollout buffer.

        Returns aggregated training metrics.
        """
        if len(self.buffer) == 0:
            return {"status": "empty_buffer"}

        # Compute GAE advantages
        with torch.no_grad():
            last_state = self.buffer.states[-1]
            _, last_value = self.policy(last_state)
            last_val = last_value.squeeze().item()

        advantages, returns = self.buffer.compute_gae(last_val)

        # Normalize advantages
        advantages = (advantages - advantages.mean()) / (advantages.std() + 1e-8)

        # Convert buffer to tensors
        states = torch.stack(self.buffer.states) if isinstance(self.buffer.states[0], torch.Tensor) else torch.tensor(self.buffer.states, dtype=torch.float32)
        actions = torch.tensor(self.buffer.actions, dtype=torch.long)
        old_log_probs = torch.tensor(self.buffer.log_probs, dtype=torch.float32)

        n = len(self.buffer)
        all_metrics: Dict[str, list] = {}

        for epoch in range(self.epochs_per_batch):
            # Shuffle indices for mini-batching
            indices = torch.randperm(n)

            for start in range(0, n, self.batch_size):
                end = min(start + self.batch_size, n)
                mb_idx = indices[start:end]

                loss, metrics = self.compute_loss(
                    states[mb_idx],
                    actions[mb_idx],
                    old_log_probs[mb_idx],
                    advantages[mb_idx],
                    returns[mb_idx],
                )

                self.optimizer.zero_grad()
                loss.backward()
                nn.utils.clip_grad_norm_(self.policy.parameters(), self.max_grad_norm)
                self.optimizer.step()

                for k, v in metrics.items():
                    all_metrics.setdefault(k, []).append(v)

        self.buffer.clear()

        # Average metrics across all mini-batches
        return {k: sum(v) / len(v) for k, v in all_metrics.items()}

    async def run_design_loop(
        self,
        target_id: str,
        project_id: str,
        config: Dict[str, Any],
        progress_callback: Any = None,
    ) -> Dict[str, Any]:
        """Full PPO molecule design loop (§84.4).

        1. Initialize molecular state (seed SMILES or random)
        2. For each step: sample action → apply modification → score via ADMET/docking
        3. When rollout buffer full → PPO update
        4. Collect top-K candidates by reward

        Args:
            target_id: Target protein ID for docking scoring
            project_id: Project context
            config: Design parameters (max_iterations, seed_smiles, etc.)
            progress_callback: Optional async callback(step, total, message)

        Returns:
            Dict with candidates list, training metrics, iteration details
        """
        from services.molecule_service import ADMETPredictor

        max_iterations = config.get("max_iterations", 100)
        seed_smiles = config.get("seed_smiles", "c1ccccc1")  # benzene default
        top_k = config.get("top_k", 10)
        run_id = config.get("run_id", project_id)

        admet = ADMETPredictor()
        candidates: List[Dict[str, Any]] = []
        training_metrics: List[Dict[str, float]] = []

        # Action space: simple molecular modifications
        ACTIONS = [
            "add_methyl", "add_hydroxyl", "add_amino", "add_fluorine",
            "add_chlorine", "add_ring", "remove_group", "cyclize",
            "add_carbonyl", "add_ether", "add_thiol", "add_nitro",
            "add_sulfonyl", "add_amide", "add_ester", "add_carboxyl",
            "scaffold_hop_1", "scaffold_hop_2", "scaffold_hop_3", "scaffold_hop_4",
            "bioisostere_1", "bioisostere_2", "bioisostere_3", "bioisostere_4",
            "ring_open", "ring_close", "chain_extend", "chain_shorten",
            "aromatic_sub", "heteroatom_swap", "stereo_flip", "terminate",
        ]

        current_smiles = seed_smiles
        episode = 0  # each reset = new episode

        for step in range(max_iterations):
            if progress_callback:
                pct = int((step / max_iterations) * 100)
                await progress_callback(
                    step, max_iterations,
                    f"Episode {episode} — step {step + 1}/{max_iterations} ({pct}%)",
                )

            try:
                # Encode current molecule as features
                state = self._encode_molecule(current_smiles)

                # Sample action from policy
                action_idx, log_prob, value = self.select_action(state)
                action_name = ACTIONS[min(action_idx, len(ACTIONS) - 1)]

                # Apply action to get new molecule
                new_smiles = self._apply_action(current_smiles, action_name)

                # Score via ADMET
                admet_result = admet.predict(new_smiles)
                reward = self._compute_reward(admet_result, new_smiles)

                done = action_name == "terminate" or step == max_iterations - 1

                # Store transition
                self.buffer.store(state, action_idx, log_prob, reward, value, done)

                # Track candidate
                candidates.append({
                    "smiles": new_smiles,
                    "reward": reward,
                    "admet": admet_result,
                    "action": action_name,
                    "step": step,
                    "episode": episode,
                })

                # PPO update when buffer is full
                if len(self.buffer) >= self.rollout_steps or done:
                    metrics = self.update()
                    training_metrics.append(metrics)
                    log.info("ppo_update", step=step, episode=episode,
                             **{k: round(v, 4) for k, v in metrics.items() if isinstance(v, float)})

                if done:
                    # Emit episode-complete progress event
                    if progress_callback:
                        await progress_callback(
                            step + 1, max_iterations,
                            f"Episode {episode} complete — resetting to seed SMILES",
                        )
                    episode += 1
                    current_smiles = seed_smiles  # Reset for next episode
                else:
                    current_smiles = new_smiles

            except Exception as exc:  # §84.4: per-episode rollback
                log.warning("ppo_episode_error", step=step, episode=episode, error=str(exc))
                self.buffer.clear()  # rollback in-progress episode buffer
                current_smiles = seed_smiles  # reset to safe state
                episode += 1
                continue

        # Sort candidates by reward and return top-K
        candidates.sort(key=lambda c: c["reward"], reverse=True)
        top_candidates = candidates[:top_k]

        # §84.5: Persist best candidates to PostgreSQL molecules table
        await self._save_candidates(top_candidates, run_id, project_id, target_id)

        return {
            "candidates": top_candidates,
            "total_iterations": max_iterations,
            "training_metrics": training_metrics,
            "target_id": target_id,
            "project_id": project_id,
        }

    async def _save_candidates(
        self,
        candidates: List[Dict[str, Any]],
        run_id: str,
        project_id: str,
        target_id: str,
    ) -> None:
        """Persist top-K candidates to the molecules table (§84.5).

        Uses AsyncSessionLocal; silently skips on any DB error to keep
        design loop non-blocking.
        """
        if not candidates:
            return
        try:
            from core.db import AsyncSessionLocal
            from sqlalchemy import text
            import json as _json
            import datetime

            async with AsyncSessionLocal() as session:
                async with session.begin():
                    for c in candidates:
                        await session.execute(
                            text(
                                "INSERT INTO molecules "
                                "(smiles, reward, run_id, project_id, target_id, "
                                "admet_json, created_at) "
                                "VALUES (:smiles, :reward, :run_id, :project_id, "
                                ":target_id, :admet_json, :created_at) "
                                "ON CONFLICT DO NOTHING"
                            ),
                            {
                                "smiles": c.get("smiles", ""),
                                "reward": float(c.get("reward", 0.0)),
                                "run_id": run_id,
                                "project_id": project_id,
                                "target_id": target_id,
                                "admet_json": _json.dumps(c.get("admet", {})),
                                "created_at": datetime.datetime.utcnow().isoformat(),
                            },
                        )
                log.info("ppo_molecules_saved", count=len(candidates), run_id=run_id)
        except Exception as exc:
            log.warning("ppo_molecule_save_failed", error=str(exc))

    def _encode_molecule(self, smiles: str) -> Any:
        """Encode SMILES as atom feature tensor for the GNN policy."""
        if not TORCH_AVAILABLE:
            raise RuntimeError("PyTorch required")

        try:
            from rdkit import Chem
            mol = Chem.MolFromSmiles(smiles)
            if mol is None:
                return torch.randn(1, 32)
            atoms = mol.GetAtoms()
            n_atoms = min(len(atoms), 64)
            features = []
            for i, atom in enumerate(atoms):
                if i >= 64:
                    break
                feat = [
                    atom.GetAtomicNum() / 100.0,
                    atom.GetDegree() / 6.0,
                    atom.GetTotalValence() / 8.0,
                    float(atom.GetIsAromatic()),
                    float(atom.IsInRing()),
                    (atom.GetFormalCharge() + 3) / 6.0,
                    atom.GetNumRadicalElectrons() / 2.0,
                    float(atom.GetHybridization()) / 6.0,
                ]
                feat.extend([0.0] * (32 - len(feat)))
                features.append(feat[:32])
            while len(features) < 1:
                features.append([0.0] * 32)
            return torch.tensor(features, dtype=torch.float32)
        except ImportError:
            # Fallback: hash-based feature vector
            h = hash(smiles) % (2**31)
            torch.manual_seed(h)
            return torch.randn(max(len(smiles) // 3, 1), 32)

    def _apply_action(self, smiles: str, action: str) -> str:
        """Apply a molecular modification action to a SMILES string.

        Uses RDKit when available; falls back to string-level heuristics.
        """
        try:
            from rdkit import Chem
            from rdkit.Chem import AllChem, rdMolDescriptors

            mol = Chem.MolFromSmiles(smiles)
            if mol is None:
                return smiles

            FRAGMENT_MAP = {
                "add_methyl": "[CH3]",
                "add_hydroxyl": "[OH]",
                "add_amino": "[NH2]",
                "add_fluorine": "[F]",
                "add_chlorine": "[Cl]",
                "add_carbonyl": "[C](=O)",
                "add_ether": "[O]",
                "add_thiol": "[SH]",
                "add_nitro": "[N+](=O)[O-]",
                "add_sulfonyl": "[S](=O)(=O)",
                "add_amide": "[C](=O)[NH]",
                "add_ester": "[C](=O)[O]",
                "add_carboxyl": "[C](=O)[OH]",
            }

            if action in FRAGMENT_MAP:
                # Add fragment to a random attachment point
                frag = FRAGMENT_MAP[action]
                new_smi = smiles.rstrip(")") + frag if ")" in smiles else smiles + frag
                test = Chem.MolFromSmiles(new_smi)
                return Chem.MolToSmiles(test) if test else smiles

            if action == "add_ring":
                return smiles + "C1CCCCC1" if len(smiles) < 100 else smiles

            if action in ("remove_group", "chain_shorten"):
                if len(smiles) > 6:
                    return smiles[:-2]
                return smiles

            if action in ("terminate",):
                return smiles

            # Default: return unchanged
            return smiles

        except ImportError:
            # String-level fallback
            if "methyl" in action:
                return smiles + "C"
            if "hydroxyl" in action:
                return smiles + "O"
            if "amino" in action:
                return smiles + "N"
            if "fluorine" in action:
                return smiles + "F"
            if "ring" in action and "add" in action:
                return smiles + "C1CCCCC1"
            return smiles

    def _compute_reward(self, admet_result: Dict[str, Any], smiles: str) -> float:
        """Compute scalar reward from ADMET predictions and molecular properties.

        R = binding_score + w_qed*QED + w_sa*(1-SA_norm) - w_tox*tox_penalty + w_nov*novelty

        Component breakdown:
          binding_score   : proxy from ADMET absorption HIA/Caco2 (0–0.5)
          QED             : drug-likeness quantitative estimate (0–1)
          SA_score        : synthetic accessibility (1=easy … 10=hard) → 1-SA/10
          tox_penalty     : hERG + hepatotox flags (0–0.5)
          novelty         : inverse of SMILES length proxy (0–0.2)

        Higher reward = better drug candidate.
        """
        reward = 0.0

        # ── Binding score proxy (absorption as surrogate) ─────────────────
        absorption = admet_result.get("absorption", {})
        binding_score = 0.0
        if isinstance(absorption, dict):
            if absorption.get("hia", "") == "high":
                binding_score += 0.3
            if absorption.get("caco2", "") == "high":
                binding_score += 0.2
        reward += binding_score

        # ── QED (Quantitative Estimate of Drug-likeness) ───────────────────
        qed_score = 0.0
        try:
            from rdkit import Chem
            from rdkit.Chem import QED as QEDModule
            mol = Chem.MolFromSmiles(smiles)
            if mol is not None:
                qed_score = QEDModule.qed(mol)
        except Exception:
            # Fallback: Lipinski-based approximation
            violations = admet_result.get("lipinski_violations", 3)
            qed_score = max(0.0, 1.0 - violations * 0.25)
        reward += 0.4 * qed_score  # weight 0.4

        # ── SA score (synthetic accessibility) ────────────────────────────
        sa_score_raw = 5.0  # neutral default
        sa_info = admet_result.get("synthetic_accessibility", {})
        if isinstance(sa_info, dict):
            sa_score_raw = float(sa_info.get("sa_score", 5.0))
        elif isinstance(sa_info, (int, float)):
            sa_score_raw = float(sa_info)
        sa_norm = 1.0 - min(sa_score_raw / 10.0, 1.0)
        reward += 0.25 * sa_norm  # weight 0.25

        # ── Toxicity penalty ──────────────────────────────────────────────
        tox_penalty = 0.0
        toxicity = admet_result.get("toxicity", {})
        if isinstance(toxicity, dict):
            if toxicity.get("herg_risk", "") == "high":
                tox_penalty += 0.3
            elif toxicity.get("herg_risk", "") == "medium":
                tox_penalty += 0.15
            if toxicity.get("hepatotoxicity_risk", "") == "high":
                tox_penalty += 0.2
        reward -= tox_penalty  # weight 1.0 (direct subtraction)

        # ── Novelty proxy (prefer shorter, less trivial SMILES) ───────────
        # Very short → trivial; very long → complex/unsynth. Sweet spot 20-60.
        slen = len(smiles)
        if 20 <= slen <= 60:
            novelty = 0.2
        elif slen < 20:
            novelty = 0.05
        else:
            novelty = max(0.0, 0.2 - (slen - 60) * 0.002)
        reward += novelty

        return reward


# ── Factory ────────────────────────────────────────────────

def create_ppo_trainer(
    atom_dim: int = 32,
    hidden_dim: int = 128,
    num_actions: int = 32,
    lr: float = 3e-4,
    **kwargs,
) -> PPOTrainer:
    """Create a PPOTrainer with a fresh MoleculeGNNPolicy.

    Falls back gracefully when PyTorch is unavailable.
    """
    if not TORCH_AVAILABLE:
        raise RuntimeError(
            "PPO training requires PyTorch. Install with: pip install torch"
        )

    from services.dl_models import MoleculeGNNPolicy

    policy = MoleculeGNNPolicy(
        atom_dim=atom_dim,
        hidden_dim=hidden_dim,
        num_actions=num_actions,
    )
    return PPOTrainer(policy=policy, lr=lr, **kwargs)
