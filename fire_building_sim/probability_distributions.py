"""Small NumPy-based distribution samplers used by stochastic components."""

import math
from typing import Optional

import numpy as np
import matplotlib.pyplot as plt


def _plot_histogram(samples, *, bins, title, xlabel):
    """Render a dependency-light diagnostic histogram."""
    plt.hist(samples, bins=bins, alpha=0.85, edgecolor="white")
    plt.title(title)
    plt.xlabel(xlabel)
    plt.ylabel("Frequency")
    plt.grid(axis="y", linestyle="--", alpha=0.35)
    plt.tight_layout()
    plt.show()

def lognormal_sampler(mean: float, std: float, rng: Optional[np.random.Generator] = None):
    """
    Create a lognormal distribution sampler from a target mean and standard deviation.

    This function takes the desired arithmetic mean (m) and standard deviation (s)
    of the lognormal distribution X, and converts them into the parameters μ and σ
    of the underlying normal distribution Y.
    Returns Callable[[int], np.ndarray]
    """
    sigma2 = math.log(1 + (std**2)/(mean**2))
    sigma = math.sqrt(sigma2)
    mu = math.log(mean) - 0.5*sigma2
    rng = rng or np.random.default_rng()
    return lambda size=1: rng.lognormal(mu, sigma, size=size)


def plot_lognormal_dist():
    """
    Plot distribution for confirmation.
    """
    sampler = lognormal_sampler(240, 60)
    samples = sampler(5000)  # 5000 draws
    _plot_histogram(
        samples,
        bins=50,
        title="ETA Distribution (Lognormal)",
        xlabel="ETA (seconds)",
    )

def normal_sampler(mean: float, std: float, rng: Optional[np.random.Generator] = None):
    """Sampler for Normal(mean, std)."""
    rng = rng or np.random.default_rng()
    return lambda size=1: rng.normal(loc=mean, scale=std, size=size)

def plot_normal_dist(mean: float = 0.0, std: float = 1.0, n: int = 5000):
    """Plot Normal samples."""
    sampler = normal_sampler(mean, std)
    samples = sampler(n)
    _plot_histogram(samples, bins=50, title=f"Normal (mean={mean}, std={std})", xlabel="Value")

def exponential_sampler(mean: float, rng: Optional[np.random.Generator] = None):
    """Sampler for Exponential with given mean (scale=mean)."""
    rng = rng or np.random.default_rng()
    return lambda size=1: rng.exponential(scale=mean, size=size)

def plot_exponential_dist(mean: float = 1.0, n: int = 5000):
    """Plot Exponential samples."""
    sampler = exponential_sampler(mean)
    samples = sampler(n)
    _plot_histogram(samples, bins=50, title=f"Exponential (mean={mean})", xlabel="Value")

def gamma_sampler(mean: float, cv: float, rng: Optional[np.random.Generator] = None):
    """
    Sampler for Gamma using mean and coefficient of variation (cv = std/mean).
    Shape k = 1/cv^2, scale θ = mean/k.
    """
    k = 1.0 / (cv**2)
    theta = mean / k
    rng = rng or np.random.default_rng()
    return lambda size=1: rng.gamma(shape=k, scale=theta, size=size)

def plot_gamma_dist(mean: float = 4.0, cv: float = 0.5, n: int = 5000):
    """Plot Gamma samples (mean & CV)."""
    sampler = gamma_sampler(mean, cv)
    samples = sampler(n)
    _plot_histogram(samples, bins=50, title=f"Gamma (mean={mean}, cv={cv})", xlabel="Value")

def weibull_sampler(shape: float, scale: float, rng: Optional[np.random.Generator] = None):
    """
    Sampler for Weibull with 'shape' (k) and 'scale' (λ).
    NumPy draws from Weibull(k) with scale=1; multiply by λ to scale.
    """
    rng = rng or np.random.default_rng()
    return lambda size=1: rng.weibull(a=shape, size=size) * scale

def plot_weibull_dist(shape: float = 2.0, scale: float = 1.0, n: int = 5000):
    """Plot Weibull samples."""
    sampler = weibull_sampler(shape, scale)
    samples = sampler(n)
    _plot_histogram(
        samples,
        bins=50,
        title=f"Weibull (shape={shape}, scale={scale})",
        xlabel="Value",
    )

def uniform_sampler(low: float, high: float, rng: Optional[np.random.Generator] = None):
    """Sampler for Uniform(low, high)."""
    rng = rng or np.random.default_rng()
    return lambda size=1: rng.uniform(low=low, high=high, size=size)

def plot_uniform_dist(low: float = 0.0, high: float = 1.0, n: int = 5000):
    """Plot Uniform samples."""
    sampler = uniform_sampler(low, high)
    samples = sampler(n)
    _plot_histogram(samples, bins=50, title=f"Uniform (low={low}, high={high})", xlabel="Value")

def beta_sampler(alpha: float, beta: float, rng: Optional[np.random.Generator] = None):
    """Sampler for Beta(alpha, beta) on [0, 1]."""
    rng = rng or np.random.default_rng()
    return lambda size=1: rng.beta(a=alpha, b=beta, size=size)

def plot_beta_dist(alpha: float = 8.0, beta: float = 2.0, n: int = 5000):
    """Plot Beta samples."""
    sampler = beta_sampler(alpha, beta)
    samples = sampler(n)
    _plot_histogram(samples, bins=50, title=f"Beta (alpha={alpha}, beta={beta})", xlabel="Value")

def bernoulli_sampler(p: float, rng: Optional[np.random.Generator] = None):
    """Sampler for Bernoulli(p). Returns 0/1 draws."""
    rng = rng or np.random.default_rng()
    return lambda size=1: (rng.random(size=size) < p).astype(int)

def plot_bernoulli_dist(p: float = 0.8, n: int = 5000):
    """Plot Bernoulli samples as counts of 0/1."""
    sampler = bernoulli_sampler(p)
    samples = sampler(n)
    values, counts = np.unique(samples, return_counts=True)
    plt.bar(values, counts, width=0.6)
    plt.title(f"Bernoulli (p={p})")
    plt.xlabel("Outcome")
    plt.ylabel("Count")
    plt.xticks([0, 1])
    plt.grid(axis="y", linestyle="--", alpha=0.35)
    plt.tight_layout()
    plt.show()
