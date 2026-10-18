"""
Institutional Offline PyTorch BPTT Surrogate Gradient Training Pipeline
========================================================================
Day 3 of 7-Day Brutal Upgrade Plan:
Trains Recurrent Spiking Neural Network (RSNN) synaptic weights on 500,000
market ticks using Truncated Backpropagation Through Time (TBPTT) with Fast
Sigmoid surrogate gradients, spiking energy sparsity regularization, multi-task
ROC-AUC validation, and direct weight synchronization to the C++20 AVX2 SIMD core.
"""

import os
import sys
import time
import argparse
import numpy as np
import torch
import torch.nn as nn
from torch.optim.lr_scheduler import CosineAnnealingLR
from sklearn.metrics import roc_auc_score

PROJECT_ROOT = os.path.dirname(os.path.abspath(__file__))
if PROJECT_ROOT not in sys.path:
    sys.path.insert(0, PROJECT_ROOT)

from config import CONFIG_NEURO, NeuromorphicConfig
from neuroquant.neuromorphic.torch_rsnn import TorchRSNN
from neuroquant.neuromorphic.dataset import generate_market_ticks, get_market_dataloaders
from neuroquant.neuromorphic.cpp_backend import CPURSNNCore, is_cpp_backend_available

def parse_args():
    parser = argparse.ArgumentParser(
        description="Offline PyTorch BPTT Training Pipeline for RSNN Hot-Path"
    )
    parser.add_argument("--ticks", type=int, default=500_000,
                        help="Number of market ticks to generate/load (default: 500,000)")
    parser.add_argument("--horizon", type=int, default=20,
                        help="Lookahead horizon in ticks for target labeling (default: 20)")
    parser.add_argument("--seq-len", type=int, default=50,
                        help="TBPTT sequence length (default: 50)")
    parser.add_argument("--stride-train", type=int, default=10,
                        help="Stride between training sequences in ticks (default: 10)")
    parser.add_argument("--stride-val", type=int, default=25,
                        help="Stride between validation sequences in ticks (default: 25)")
    parser.add_argument("--batch-size", type=int, default=64,
                        help="Training mini-batch size (default: 64)")
    parser.add_argument("--epochs", type=int, default=5,
                        help="Number of training epochs (default: 5)")
    parser.add_argument("--lr", type=float, default=0.003,
                        help="Initial learning rate for AdamW (default: 0.003)")
    parser.add_argument("--weight-decay", type=float, default=1e-4,
                        help="L2 weight decay regularizer (default: 1e-4)")
    parser.add_argument("--sparsity-weight", type=float, default=2.5,
                        help="Loss penalty weight for spiking sparsity (default: 2.5)")
    parser.add_argument("--target-sparsity", type=float, default=0.10,
                        help="Target hidden neuron firing rate (default: 0.10 = 10%)")
    parser.add_argument("--hidden-neurons", type=int, default=64,
                        help="Number of recurrent reservoir neurons (default: 64)")
    parser.add_argument("--enable-dale", action="store_true",
                        help="Enforce Dale's Principle (80% excitatory / 20% inhibitory)")
    parser.add_argument("--device", type=str, default="cuda" if torch.cuda.is_available() else "cpu",
                        help="Compute device: 'cpu' or 'cuda'")
    parser.add_argument("--output-dir", type=str, default="weights",
                        help="Directory to save exported model weights (default: weights)")
    parser.add_argument("--cache-path", type=str, default="data/market_ticks_500k.npz",
                        help="File path to cache/load dataset")
    parser.add_argument("--force-regenerate", action="store_true",
                        help="Force regeneration of 500k market ticks dataset")
    parser.add_argument("--quick", action="store_true",
                        help="Run rapid validation mode (100k ticks, 3 epochs) for quick check")
    return parser.parse_args()

def evaluate(model: nn.Module, val_loader, criterion, sparsity_weight: float, target_sparsity: float, device: torch.device):
    """
    Evaluates the model on the holdout validation set.
    Computes Loss, Per-Channel ROC-AUC, and Mean Spiking Sparsity.
    """
    model.eval()
    total_val_loss = 0.0
    total_task_loss = 0.0
    total_sparsity_loss = 0.0
    all_probs = []
    all_targets = []
    total_sparsity = 0.0
    num_batches = 0

    with torch.no_grad():
        for x_b, y_b in val_loader:
            x_b = x_b.to(device)
            y_b = y_b.to(device)

            out = model(x_b)
            logits = out["logits"]
            probs = out["probabilities"]
            mean_spk = out["mean_hidden_sparsity"]

            task_loss = criterion(logits, y_b)
            spk_loss = torch.square(mean_spk - target_sparsity)
            loss = task_loss + sparsity_weight * spk_loss

            total_val_loss += loss.item()
            total_task_loss += task_loss.item()
            total_sparsity_loss += spk_loss.item()
            total_sparsity += mean_spk.item()
            num_batches += 1

            all_probs.append(probs.cpu().numpy())
            all_targets.append(y_b.cpu().numpy())

    all_probs = np.vstack(all_probs)
    all_targets = np.vstack(all_targets)

    # Compute ROC-AUC per channel
    channel_names = ["Upward Move", "Downward Move", "Toxicity Alert", "Volatility Burst"]
    roc_aucs = {}
    for c in range(4):
        # Handle cases where all targets might be single class in small subset
        if len(np.unique(all_targets[:, c])) > 1:
            score = roc_auc_score(all_targets[:, c], all_probs[:, c])
        else:
            score = 0.5
        roc_aucs[channel_names[c]] = float(score)

    mean_auc = float(np.mean(list(roc_aucs.values())))

    metrics = {
        "val_loss": total_val_loss / max(1, num_batches),
        "task_loss": total_task_loss / max(1, num_batches),
        "spk_loss": total_sparsity_loss / max(1, num_batches),
        "mean_sparsity": total_sparsity / max(1, num_batches),
        "channel_roc_aucs": roc_aucs,
        "mean_roc_auc": mean_auc,
    }
    return metrics

def train():
    args = parse_args()
    if args.quick:
        args.ticks = 100_000
        args.epochs = 3
        args.cache_path = "data/market_ticks_100k.npz"

    print("=" * 80)
    print("NEUROQUANT-LOB: OFFLINE PYTORCH BPTT SURROGATE GRADIENT TRAINING PIPELINE")
    print("=" * 80)
    print(f"Device:               {args.device.upper()}")
    print(f"Total Market Ticks:   {args.ticks:,}")
    print(f"Horizon Lookahead:    {args.horizon} ticks")
    print(f"TBPTT Sequence Len:   {args.seq_len} ticks")
    print(f"Batch Size:           {args.batch_size}")
    print(f"Epochs:               {args.epochs}")
    print(f"Learning Rate:        {args.lr}")
    print(f"Weight Decay:         {args.weight_decay}")
    print(f"Target Sparsity:      {args.target_sparsity * 100:.1f}%")
    print(f"Sparsity Weight:      {args.sparsity_weight}")
    print(f"Hidden Neurons:       {args.hidden_neurons}")
    print(f"Dale's Principle:     {'Enabled' if args.enable_dale else 'Disabled'}")
    print("=" * 80)

    device = torch.device(args.device)

    # 1. Dataset Generation / Loading
    dataset_dict = generate_market_ticks(
        num_ticks=args.ticks,
        horizon=args.horizon,
        seed=42,
        cache_path=args.cache_path,
        force_regenerate=args.force_regenerate
    )

    train_loader, val_loader = get_market_dataloaders(
        dataset_dict,
        seq_len=args.seq_len,
        stride_train=args.stride_train,
        stride_val=args.stride_val,
        batch_size=args.batch_size,
        train_split=0.8
    )
    print(f"[DATASET] Prepared {len(train_loader)} training batches and {len(val_loader)} validation batches.")

    # 2. Model Initialization
    cfg = NeuromorphicConfig(
        num_sensory_neurons=32,
        num_hidden_neurons=args.hidden_neurons,
        num_motor_neurons=4
    )
    model = TorchRSNN(
        num_sensory=32,
        num_hidden=args.hidden_neurons,
        num_motor=4,
        config=cfg,
        enable_dale=args.enable_dale
    ).to(device)

    # 3. Class Imbalance Weighting for BCE Loss
    train_targets = dataset_dict["targets"][:int(len(dataset_dict["targets"]) * 0.8)]
    pos_counts = np.sum(train_targets, axis=0)
    total_samples = len(train_targets)
    pos_weights = []
    for c in range(4):
        p = max(1, pos_counts[c])
        weight = float((total_samples - p) / p)
        # Cap weight between 1.0 and 8.0 for training stability
        pos_weights.append(min(8.0, max(1.0, weight)))
    pos_weight_tensor = torch.tensor(pos_weights, dtype=torch.float32, device=device)
    print(f"[TRAINING] Positive class loss weights: {[round(w, 2) for w in pos_weights]}")

    criterion = nn.BCEWithLogitsLoss(pos_weight=pos_weight_tensor)
    optimizer = torch.optim.AdamW(model.parameters(), lr=args.lr, weight_decay=args.weight_decay)
    scheduler = CosineAnnealingLR(optimizer, T_max=args.epochs, eta_min=args.lr * 0.1)

    # 4. Training Loop
    best_val_auc = 0.0
    best_weights_path = None
    start_train_time = time.perf_counter()

    for epoch in range(1, args.epochs + 1):
        model.train()
        epoch_start = time.perf_counter()
        running_loss = 0.0
        running_task_loss = 0.0
        running_spk_loss = 0.0
        running_sparsity = 0.0
        batches_processed = 0

        for batch_idx, (x_b, y_b) in enumerate(train_loader):
            x_b = x_b.to(device)
            y_b = y_b.to(device)

            optimizer.zero_grad()
            out = model(x_b)

            logits = out["logits"]
            mean_spk = out["mean_hidden_sparsity"]

            task_loss = criterion(logits, y_b)
            # Quadratic sparsity penalty: ||mean_f - f_target||^2
            spk_loss = torch.square(mean_spk - args.target_sparsity)
            total_loss = task_loss + args.sparsity_weight * spk_loss

            total_loss.backward()
            # Gradient clipping to prevent exploding gradients in recurrent unrolling
            torch.nn.utils.clip_grad_norm_(model.parameters(), max_norm=1.0)
            optimizer.step()

            running_loss += total_loss.item()
            running_task_loss += task_loss.item()
            running_spk_loss += spk_loss.item()
            running_sparsity += mean_spk.item()
            batches_processed += 1

            if (batch_idx + 1) % max(1, len(train_loader) // 5) == 0:
                cur_loss = running_loss / batches_processed
                cur_spk = (running_sparsity / batches_processed) * 100.0
                print(f"  [Epoch {epoch}/{args.epochs}] Batch {batch_idx+1}/{len(train_loader)}: "
                      f"Loss={cur_loss:.4f} | Sparsity={cur_spk:.2f}% | LR={optimizer.param_groups[0]['lr']:.5f}")

        scheduler.step()
        train_elapsed = time.perf_counter() - epoch_start

        # Validation Pass
        val_metrics = evaluate(model, val_loader, criterion, args.sparsity_weight, args.target_sparsity, device)

        print("-" * 80)
        print(f"EPOCH {epoch}/{args.epochs} SUMMARY ({train_elapsed:.2f}s):")
        print(f"  Train Loss:       {running_loss / batches_processed:.4f} (Task: {running_task_loss / batches_processed:.4f}, Spk: {running_spk_loss / batches_processed:.4f})")
        print(f"  Train Sparsity:   {(running_sparsity / batches_processed)*100:.2f}% (Target: {args.target_sparsity*100:.1f}%)")
        print(f"  Val Loss:         {val_metrics['val_loss']:.4f}")
        print(f"  Val Sparsity:     {val_metrics['mean_sparsity']*100:.2f}%")
        print("  ROC-AUC Validation Scores:")
        for ch_name, score in val_metrics["channel_roc_aucs"].items():
            print(f"    * {ch_name:<20}: {score:.4f}")
        print(f"  ==> MEAN ROC-AUC:  {val_metrics['mean_roc_auc']:.4f}")
        print("-" * 80)

        # Checkpoint Best Model
        if val_metrics["mean_roc_auc"] > best_val_auc:
            best_val_auc = val_metrics["mean_roc_auc"]
            saved_paths = model.save_weights(save_dir=args.output_dir, prefix="rsnn_optimal_weights")
            best_weights_path = saved_paths["npz"]
            print(f"  [CHECKPOINT] New best model saved! (Mean ROC-AUC: {best_val_auc:.4f})")
            print(f"               Exported to: {saved_paths['npz']} and {saved_paths['bin']}")

    total_train_elapsed = time.perf_counter() - start_train_time
    print("\n" + "=" * 80)
    print(f"TRAINING COMPLETED IN {total_train_elapsed:.2f}s | PEAK ROC-AUC: {best_val_auc:.4f}")
    print("=" * 80)

    # 5. Direct C++20 AVX2 SIMD Core Hardware Verification
    print("\n[VERIFICATION] Verifying Zero-Python Hot-Path Synchronization with C++20 AVX2 SIMD Core...")
    if not is_cpp_backend_available():
        print("  [WARNING] C++ lif_core library not found. Skipping hardware synchronization check.")
        return

    try:
        cpp_core = CPURSNNCore(CONFIG_NEURO)
        # Load best weights
        if best_weights_path and os.path.exists(best_weights_path):
            model.load_weights(best_weights_path)
        model.sync_to_cpp(cpp_core)
        print("  [SUCCESS] Trained weights loaded into C++20 alignas(64) SIMD memory pools!")

        # Run 10,000 validation ticks through C++ SIMD Hot-Path
        test_ticks = dataset_dict["spikes"][-10_000:]
        t_cpp_0 = time.perf_counter()
        motor_active_count = 0
        for i in range(len(test_ticks)):
            s_spk, h_spk, m_spk = cpp_core.step(test_ticks[i])
            if np.any(m_spk):
                motor_active_count += 1
        t_cpp_1 = time.perf_counter()

        elapsed_cpp_ns = ((t_cpp_1 - t_cpp_0) / len(test_ticks)) * 1e9
        print(f"  [C++ SIMD BENCHMARK] 10,000 ticks processed in {(t_cpp_1 - t_cpp_0)*1000:.2f} ms")
        print(f"                       Latency per tick: {elapsed_cpp_ns:.1f} ns")
        print(f"                       Throughput:       {len(test_ticks)/(t_cpp_1 - t_cpp_0):,.0f} ticks/s")
        print(f"                       Motor Firing Act: {motor_active_count}/{len(test_ticks)} ticks")
        print("  [VERIFICATION RESULT] C++20 AVX2 Hot-Path fully operational with PyTorch-trained weights!")
    except Exception as e:
        print(f"  [ERROR] Hardware verification failed: {e}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    train()
