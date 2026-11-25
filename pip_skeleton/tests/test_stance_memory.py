"""§6.4 立场知识层（可积累、自我校准）——先写测试，后写实现。"""

import math
import random
import unittest

from pip.stance_memory import (
    DEFAULT_PRIOR_WEIGHT,
    StanceMemory,
    calibration,
    decide_rollback,
    exploration_sample,
)


def make_memory():
    return StanceMemory(":memory:")


class ProfileAccumulationTest(unittest.TestCase):
    def test_new_source_is_neutral_and_unconfident(self):
        mem = make_memory()
        profile = mem.profile("src-a")
        self.assertEqual(profile.lean, 0.0)
        self.assertEqual(profile.n_obs, 0)
        self.assertAlmostEqual(mem.confidence(0), 0.0)

    def test_single_observation_shrinks_toward_prior(self):
        mem = make_memory()
        mem.observe("src-a", event="e1", dimension="framing", value=1.0)
        profile = mem.profile("src-a")
        expected = 1.0 / (1 + DEFAULT_PRIOR_WEIGHT)
        self.assertAlmostEqual(profile.lean, expected, places=6)

    def test_confidence_increases_with_observations(self):
        mem = make_memory()
        confs = []
        for i in range(10):
            mem.observe("src-a", event=f"e{i}", dimension="framing", value=0.5)
            confs.append(mem.confidence(mem.profile("src-a").n_obs))
        self.assertEqual(confs, sorted(confs))
        self.assertGreater(confs[-1], 0.6)

    def test_opposite_observations_cancel(self):
        mem = make_memory()
        for i in range(6):
            mem.observe("src-a", event=f"p{i}", dimension="framing", value=1.0)
            mem.observe("src-a", event=f"n{i}", dimension="framing", value=-1.0)
        self.assertAlmostEqual(mem.profile("src-a").lean, 0.0, places=6)


class ConflictTest(unittest.TestCase):
    def test_same_event_opposite_signal_flagged_as_conflict(self):
        mem = make_memory()
        first = mem.observe("src-a", event="e1", dimension="framing", value=1.0)
        second = mem.observe("src-a", event="e1", dimension="framing", value=-1.0)
        self.assertFalse(first.conflict)
        self.assertTrue(second.conflict)

    def test_conflicts_are_preserved_not_overwritten(self):
        mem = make_memory()
        mem.observe("src-a", event="e1", dimension="framing", value=1.0)
        mem.observe("src-a", event="e1", dimension="framing", value=-1.0)
        self.assertEqual(mem.observation_count("src-a"), 2)
        self.assertEqual(len(mem.conflicts()), 1)


class SelfEvolutionTest(unittest.TestCase):
    """核心断言：样本积累必须带来可测的准确率提升，否则「自我进化」只是说法。"""

    def _simulate(self, sources=40, rounds=12, seed=7):
        rng = random.Random(seed)
        truth = {f"src-{i}": rng.choice([-1, 1]) for i in range(sources)}
        mem = make_memory()
        early, late = [], []
        for round_idx in range(rounds):
            for source, true_lean in truth.items():
                observed = 0.4 * true_lean + rng.gauss(0, 1.0)
                mem.observe(source, event=f"e{round_idx}", dimension="framing", value=observed)
            if round_idx in (1, rounds - 1):
                bucket = early if round_idx == 1 else late
                for source, true_lean in truth.items():
                    predicted = mem.predict(source).direction
                    bucket.append(1.0 if predicted == true_lean else 0.0)
        return sum(early) / len(early), sum(late) / len(late)

    def test_accuracy_improves_with_accumulated_evidence(self):
        early, late = self._simulate()
        self.assertGreater(late, early + 0.05)
        self.assertGreaterEqual(late, 0.80)

    def test_predict_exposes_uncertainty_that_shrinks(self):
        mem = make_memory()
        for i in range(2):
            mem.observe("src-a", event=f"e{i}", dimension="framing", value=1.0)
        wide = mem.predict("src-a").uncertainty
        for i in range(20):
            mem.observe("src-a", event=f"x{i}", dimension="framing", value=1.0)
        narrow = mem.predict("src-a").uncertainty
        self.assertGreater(wide, narrow)
        self.assertLess(narrow, 0.25)


class ExplorationTest(unittest.TestCase):
    def test_exploration_quota_picks_low_confidence_sources(self):
        mem = make_memory()
        for i in range(20):
            mem.observe(f"well-known-{i}", event="e", dimension="framing", value=1.0)
        sources = [f"well-known-{i}" for i in range(20)] + ["fresh-1", "fresh-2"]
        picked = exploration_sample(sources, mem, ratio=0.15, rng=random.Random(1))
        self.assertGreaterEqual(len(picked), math.ceil(0.15 * len(sources)))
        self.assertTrue({"fresh-1", "fresh-2"} & set(picked))


class CalibrationTest(unittest.TestCase):
    def test_perfect_calibration_has_near_zero_error(self):
        pairs = [(0.6, True)] * 6 + [(0.6, False)] * 4
        result = calibration(pairs)
        self.assertAlmostEqual(result.accuracy, 0.6, places=6)
        self.assertLess(result.ece, 0.02)

    def test_overconfidence_is_penalized(self):
        pairs = [(1.0, True)] * 6 + [(1.0, False)] * 4
        result = calibration(pairs)
        self.assertGreater(result.ece, 0.3)

    def test_empty_input(self):
        result = calibration([])
        self.assertEqual(result.accuracy, 0.0)
        self.assertEqual(result.n, 0)

    def test_rollback_when_below_baseline(self):
        self.assertTrue(decide_rollback(0.62, baseline=0.80))
        self.assertFalse(decide_rollback(0.85, baseline=0.80))


if __name__ == "__main__":
    unittest.main()
