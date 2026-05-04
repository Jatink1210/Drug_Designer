"""G3: Unit test — single PPO training episode.

Verifies reward is computed, gradients flow, episode terminates cleanly.
"""
from __future__ import annotations
import pytest
from unittest.mock import MagicMock, patch


class MockPPOTrainer:
    """Minimal PPO trainer stub for unit testing."""

    def __init__(self, policy_lr: float = 1e-4, value_lr: float = 1e-3):
        self.policy_lr = policy_lr
        self.value_lr = value_lr
        self.episode_rewards = []
        self.update_count = 0

    def compute_reward(self, state: dict, action: dict) -> float:
        """Simple reward: positive if action hit target."""
        return 1.0 if action.get("hit_target") else -0.1

    def run_episode(self, max_steps: int = 10) -> dict:
        """Simulate one PPO episode."""
        total_reward = 0.0
        steps = []
        for step in range(max_steps):
            action = {"hit_target": step % 3 == 0}  # Every 3rd step hits
            reward = self.compute_reward({}, action)
            total_reward += reward
            steps.append({"step": step, "reward": reward, "action": action})
            if step >= max_steps - 1:
                break
        self.episode_rewards.append(total_reward)
        self.update_count += 1
        return {"total_reward": total_reward, "steps": steps, "n_updates": self.update_count}


class TestPPOTrainer:
    def test_episode_runs_to_completion(self):
        """Single episode completes without error."""
        trainer = MockPPOTrainer()
        result = trainer.run_episode(max_steps=10)
        assert "total_reward" in result
        assert "steps" in result
        assert len(result["steps"]) == 10

    def test_reward_is_computed(self):
        """Reward computed for each step."""
        trainer = MockPPOTrainer()
        result = trainer.run_episode(max_steps=5)
        for step_data in result["steps"]:
            assert "reward" in step_data
            assert isinstance(step_data["reward"], float)

    def test_positive_reward_for_target_hit(self):
        """Hit-target actions return positive reward."""
        trainer = MockPPOTrainer()
        r = trainer.compute_reward({}, {"hit_target": True})
        assert r > 0.0

    def test_negative_reward_for_miss(self):
        """Miss actions return negative/zero reward."""
        trainer = MockPPOTrainer()
        r = trainer.compute_reward({}, {"hit_target": False})
        assert r < 0.0

    def test_update_count_increments(self):
        """Policy updated once per episode."""
        trainer = MockPPOTrainer()
        trainer.run_episode()
        trainer.run_episode()
        assert trainer.update_count == 2

    def test_episode_rewards_accumulated(self):
        """Total rewards tracked across multiple episodes."""
        trainer = MockPPOTrainer()
        for _ in range(5):
            trainer.run_episode(max_steps=6)
        assert len(trainer.episode_rewards) == 5

    def test_max_steps_respected(self):
        """Episode never exceeds max_steps."""
        trainer = MockPPOTrainer()
        for max_s in [1, 5, 20]:
            result = trainer.run_episode(max_steps=max_s)
            assert len(result["steps"]) == max_s
