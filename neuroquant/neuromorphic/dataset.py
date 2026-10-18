"""
Market Tick Dataset Pipeline for Surrogate Gradient BPTT RSNN Training
========================================================================
High-throughput generation and PyTorch Dataset abstraction for 500,000
high-frequency market ticks with Hawkes point processes, L2 order book
transitions, 32-channel sensory spike encoding, and multi-horizon targets.
"""

import os
import time
import numpy as np
import torch
from torch.utils.data import Dataset, DataLoader
from typing import Tuple, Dict, Any, Optional

from config import CONFIG_MARKET, CONFIG_NEURO, MarketConfig, NeuromorphicConfig
from neuroquant.market.order_book import OrderBook
from neuroquant.market.feed_simulator import HawkesMarketFeed
from neuroquant.neuromorphic.encoders import LOBSpikeEncoder

def generate_market_ticks(
    num_ticks: int = 500_000,
    horizon: int = 20,
    seed: int = 42,
    cache_path: Optional[str] = "data/market_ticks_500k.npz",
    force_regenerate: bool = False
) -> Dict[str, np.ndarray]:
    """
    Generates or loads 500,000 market ticks with full 32-channel sensory spike vectors
    and 4-channel ground-truth multi-horizon prediction targets.
    
    Targets (Horizon H ticks):
      - [0]: Upward Price Movement (Mid-price increases by >= 1 tick)
      - [1]: Downward Price Movement (Mid-price decreases by >= 1 tick)
      - [2]: Toxicity Alert (Aggressive institutional sweep occurs within horizon)
      - [3]: Volatility Burst (Realized tick volatility in top 15% within horizon)
      
    Returns:
      Dictionary with 'spikes' (shape: [num_ticks, 32], uint8),
      'targets' (shape: [num_ticks, 4], float32),
      'prices' (shape: [num_ticks], float32),
      'timestamps' (shape: [num_ticks], float32).
    """
    if cache_path and os.path.exists(cache_path) and not force_regenerate:
        print(f"[DATASET] Loading cached dataset from {cache_path}...")
        data = np.load(cache_path)
        if len(data["spikes"]) >= num_ticks:
            return {
                "spikes": data["spikes"][:num_ticks],
                "targets": data["targets"][:num_ticks],
                "prices": data["prices"][:num_ticks],
                "timestamps": data["timestamps"][:num_ticks]
            }
        print(f"[DATASET] Cached dataset has {len(data['spikes'])} ticks < requested {num_ticks}. Regenerating...")

    print(f"[DATASET] Generating {num_ticks:,} realistic market ticks via Hawkes Point Process & L2 LOB Engine...")
    t0 = time.perf_counter()
    np.random.seed(seed)

    mkt_cfg = MarketConfig()
    neuro_cfg = NeuromorphicConfig()

    book = OrderBook(mkt_cfg)
    feed = HawkesMarketFeed(book, mkt_cfg)
    encoder = LOBSpikeEncoder(mkt_cfg, neuro_cfg)

    spikes_arr = np.zeros((num_ticks, 32), dtype=np.uint8)
    prices_arr = np.zeros(num_ticks, dtype=np.float32)
    timestamps_arr = np.zeros(num_ticks, dtype=np.float32)
    toxic_event_flags = np.zeros(num_ticks, dtype=np.uint8)

    dt_ms = neuro_cfg.time_step_ms
    dt_sec = dt_ms / 1000.0
    sim_time_ms = 0.0

    report_interval = max(50_000, num_ticks // 10)

    for i in range(num_ticks):
        sim_time_ms += dt_ms
        snapshot, event_desc = feed.step(dt_sec)
        spk = encoder.encode(snapshot, sim_time_ms)
        spikes_arr[i] = spk.astype(np.uint8)
        prices_arr[i] = snapshot.get("mid_price", mkt_cfg.initial_mid_price)
        timestamps_arr[i] = sim_time_ms

        if "TOXIC_SWEEP" in event_desc:
            toxic_event_flags[i] = 1

        if (i + 1) % report_interval == 0 or (i + 1) == num_ticks:
            elapsed = time.perf_counter() - t0
            rate = (i + 1) / max(1e-5, elapsed)
            print(f"  -> Generated {i + 1:,} / {num_ticks:,} ticks ({rate:.0f} ticks/s)...")

    # Compute Ground-Truth Multi-Horizon Targets
    print(f"[DATASET] Labeling multi-horizon prediction targets (H = {horizon} ticks)...")
    targets_arr = np.zeros((num_ticks, 4), dtype=np.float32)
    tick_sz = mkt_cfg.tick_size

    # Strictly causal forward window lookahead: [t + 1 : t + H]
    valid_len = num_ticks - horizon
    future_p = prices_arr[horizon:]
    current_p = prices_arr[:valid_len]
    delta_future_p = future_p - current_p

    # Target 0: Upward tick move >= 1 tick size
    targets_arr[:valid_len, 0] = (delta_future_p >= tick_sz).astype(np.float32)
    # Target 1: Downward tick move <= -1 tick size
    targets_arr[:valid_len, 1] = (delta_future_p <= -tick_sz).astype(np.float32)

    # Target 2: Toxicity alert if toxic sweep occurs in future window [t + 1, t + H]
    cumsum_toxic = np.cumsum(np.concatenate(([0], toxic_event_flags)))
    future_toxic_counts = cumsum_toxic[horizon + 1:] - cumsum_toxic[1:valid_len + 1]
    targets_arr[:valid_len, 2] = (future_toxic_counts > 0).astype(np.float32)

    # Target 3: Realized volatility burst (future price variance in top 20%)
    price_diffs_sq = np.square(np.diff(prices_arr))
    cumsum_sq = np.cumsum(np.concatenate(([0], price_diffs_sq)))
    future_sq_sum = cumsum_sq[horizon:] - cumsum_sq[:valid_len]
    future_rv = np.sqrt(np.maximum(0.0, future_sq_sum))
    rv_thresh = np.percentile(future_rv, 80.0)
    targets_arr[:valid_len, 3] = (future_rv >= rv_thresh).astype(np.float32)

    # Zero out targets at trailing boundary edge
    targets_arr[valid_len:] = 0.0

    total_time = time.perf_counter() - t0
    print(f"[DATASET] Generation complete in {total_time:.2f}s! Target distribution:")
    print(f"  - Target 0 (Upward Move):     {np.mean(targets_arr[:valid_len, 0])*100:.2f}% positive")
    print(f"  - Target 1 (Downward Move):   {np.mean(targets_arr[:valid_len, 1])*100:.2f}% positive")
    print(f"  - Target 2 (Toxicity Alert):  {np.mean(targets_arr[:valid_len, 2])*100:.2f}% positive")
    print(f"  - Target 3 (Volatility Burst):{np.mean(targets_arr[:valid_len, 3])*100:.2f}% positive")

    result = {
        "spikes": spikes_arr,
        "targets": targets_arr,
        "prices": prices_arr,
        "timestamps": timestamps_arr
    }

    if cache_path:
        os.makedirs(os.path.dirname(cache_path), exist_ok=True)
        print(f"[DATASET] Caching {num_ticks:,} ticks to {cache_path}...")
        np.savez_compressed(
            cache_path,
            spikes=spikes_arr,
            targets=targets_arr,
            prices=prices_arr,
            timestamps=timestamps_arr
        )
        print(f"[DATASET] Dataset cached successfully ({os.path.getsize(cache_path) / (1024*1024):.2f} MB).")

    return result

class MarketTickDataset(Dataset):
    """
    PyTorch Dataset slicing long market tick streams into temporal sequences
    of length `seq_len` for Truncated BPTT surrogate gradient training.
    """
    def __init__(self,
                 spikes: np.ndarray,
                 targets: np.ndarray,
                 seq_len: int = 50,
                 stride: Optional[int] = None):
        super().__init__()
        self.seq_len = seq_len
        self.stride = stride if stride is not None else seq_len
        self.spikes = spikes
        self.targets = targets

        num_ticks = len(spikes)
        # Compute valid starting indices
        self.valid_indices = [
            i for i in range(0, num_ticks - seq_len, self.stride)
        ]

    def __len__(self) -> int:
        return len(self.valid_indices)

    def __getitem__(self, idx: int) -> Tuple[torch.Tensor, torch.Tensor]:
        start = self.valid_indices[idx]
        end = start + self.seq_len

        # Sensory spike window [seq_len, 32]
        x = torch.from_numpy(self.spikes[start:end]).float()
        # Ground-truth multi-target at the end of the sequence [4]
        y = torch.from_numpy(self.targets[end - 1]).float()
        return x, y

def get_market_dataloaders(
    dataset_dict: Dict[str, np.ndarray],
    seq_len: int = 50,
    stride_train: int = 10,
    stride_val: int = 25,
    batch_size: int = 64,
    train_split: float = 0.8,
    num_workers: int = 0
) -> Tuple[DataLoader, DataLoader]:
    """
    Splits market ticks into Train and Holdout Validation DataLoaders.
    Strict chronological partition without lookahead contamination.
    """
    total_ticks = len(dataset_dict["spikes"])
    train_cutoff = int(total_ticks * train_split)

    train_spikes = dataset_dict["spikes"][:train_cutoff]
    train_targets = dataset_dict["targets"][:train_cutoff]

    val_spikes = dataset_dict["spikes"][train_cutoff:]
    val_targets = dataset_dict["targets"][train_cutoff:]

    train_ds = MarketTickDataset(train_spikes, train_targets, seq_len=seq_len, stride=stride_train)
    val_ds = MarketTickDataset(val_spikes, val_targets, seq_len=seq_len, stride=stride_val)

    train_loader = DataLoader(
        train_ds,
        batch_size=batch_size,
        shuffle=True,
        drop_last=True,
        num_workers=num_workers
    )

    val_loader = DataLoader(
        val_ds,
        batch_size=batch_size,
        shuffle=False,
        drop_last=False,
        num_workers=num_workers
    )

    return train_loader, val_loader
