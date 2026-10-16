"""Synthetic lab reports, degradations, seed-demo, eval harness."""

__all__ = ["generate_all", "run_eval", "seed_demo"]


def generate_all(*args, **kwargs):
    from app.synth.generate import generate_all as _g

    return _g(*args, **kwargs)


def run_eval(*args, **kwargs):
    from app.synth.eval_harness import run_eval as _e

    return _e(*args, **kwargs)


def seed_demo(*args, **kwargs):
    from app.synth.seed_demo import seed_demo as _s

    return _s(*args, **kwargs)
