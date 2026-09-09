"""
Master Hybrid Training Engine:
Fuses Kaggle DEEP-VOICE Real-World Speech Benchmark (1,470 samples)
WITH Diverse Synthetic Vocoders & Acoustic Replay Attacks (300 samples).
Produces a maximally generalized model resilient against out-of-domain transfer.
"""

import os
import sys
import numpy as np
import torch
import torch.nn as nn
from torch.utils.data import TensorDataset, DataLoader
from sklearn.model_selection import train_test_split
from sklearn.metrics import accuracy_score, precision_score, recall_score, f1_score, confusion_matrix

PROJECT_ROOT = os.path.dirname(os.path.abspath(__file__))
if PROJECT_ROOT not in sys.path:
    sys.path.insert(0, PROJECT_ROOT)

from core.conformer_model import EnterpriseVoiceConformer


DEEPVOICE_CACHE = os.path.join(PROJECT_ROOT, "data", "deepvoice_cached_features.npz")
SYNTH_CACHE = os.path.join(PROJECT_ROOT, "data", "cached_features.npz")
CHECKPOINT_PATH = os.path.join(PROJECT_ROOT, "models", "acoustic_prosodic_net.pth")
METRICS_PATH = os.path.join(PROJECT_ROOT, "models", "training_metrics.json")


def train_hybrid_master(epochs: int = 25, batch_size: int = 32, lr: float = 1e-3):
    print("=" * 80)
    print("🚀 TRAINING MASTER GENERALIZED ACOUSTIC-PROSODIC NET")
    print("   Combining Kaggle DEEP-VOICE Dataset + Diverse Neural Vocoder & Replay Attacks")
    print("=" * 80)

    # 1. Load both datasets
    d_dv = np.load(DEEPVOICE_CACHE)
    X_dv, y_dv = d_dv["X"], d_dv["y"]
    print(f"Loaded Kaggle DEEP-VOICE: {len(y_dv)} samples (Real: {(y_dv==0).sum()}, Fake: {(y_dv==1).sum()})")

    d_syn = np.load(SYNTH_CACHE)
    X_syn, y_syn = d_syn["X"], d_syn["y"]
    print(f"Loaded Neural Vocoder & Replay Set: {len(y_syn)} samples (Real: {(y_syn==0).sum()}, Fake: {(y_syn==1).sum()})")

    # 2. Merge and balance
    X = np.concatenate([X_dv, X_syn], axis=0)
    y = np.concatenate([y_dv, y_syn], axis=0)

    perm = np.random.permutation(len(y))
    X, y = X[perm], y[perm]

    print(f"\nUnified Master Dataset Size: {len(y)} samples (Real: {(y==0).sum()}, Fake: {(y==1).sum()})")
    print(f"Tensor Shape: {X.shape}")

    # 3. Stratified Split (70% Train, 15% Val, 15% Test)
    X_train, X_temp, y_train, y_temp = train_test_split(X, y, test_size=0.30, random_state=42, stratify=y)
    X_val, X_test, y_val, y_test = train_test_split(X_temp, y_temp, test_size=0.50, random_state=42, stratify=y_temp)

    print(f"Split distribution: Train={len(y_train)}, Val={len(y_val)}, Test={len(y_test)}")

    device = "cuda" if torch.cuda.is_available() else "cpu"
    print(f"Compute Device: {device.upper()}")

    train_loader = DataLoader(TensorDataset(torch.from_numpy(X_train).float(), torch.from_numpy(y_train).long()), batch_size=batch_size, shuffle=True)
    val_loader = DataLoader(TensorDataset(torch.from_numpy(X_val).float(), torch.from_numpy(y_val).long()), batch_size=batch_size, shuffle=False)
    test_loader = DataLoader(TensorDataset(torch.from_numpy(X_test).float(), torch.from_numpy(y_test).long()), batch_size=batch_size, shuffle=False)

    model = EnterpriseVoiceConformer(input_dim=32, d_model=64, num_layers=2, num_heads=4).to(device)
    criterion = nn.CrossEntropyLoss()
    optimizer = torch.optim.AdamW(model.parameters(), lr=lr, weight_decay=1e-4)
    scheduler = torch.optim.lr_scheduler.CosineAnnealingLR(optimizer, T_max=epochs)

    best_val_loss = float("inf")
    history = []

    print(f"\nTraining for {epochs} epochs...")
    for epoch in range(1, epochs + 1):
        model.train()
        train_loss, train_correct, total_train = 0.0, 0, 0
        for bx, by in train_loader:
            bx, by = bx.to(device), by.to(device)
            optimizer.zero_grad()
            logits, _ = model(bx)
            loss = criterion(logits, by)
            loss.backward()
            nn.utils.clip_grad_norm_(model.parameters(), 1.0)
            optimizer.step()

            train_loss += loss.item() * len(by)
            train_correct += (torch.argmax(logits, dim=1) == by).sum().item()
            total_train += len(by)

        scheduler.step()
        train_loss /= total_train
        train_acc = train_correct / total_train

        # Validation
        model.eval()
        val_loss, val_correct, total_val = 0.0, 0, 0
        with torch.no_grad():
            for bx, by in val_loader:
                bx, by = bx.to(device), by.to(device)
                logits, _ = model(bx)
                loss = criterion(logits, by)
                val_loss += loss.item() * len(by)
                val_correct += (torch.argmax(logits, dim=1) == by).sum().item()
                total_val += len(by)

        val_loss /= total_val
        val_acc = val_correct / total_val

        history.append({
            "epoch": epoch,
            "train_loss": round(train_loss, 4),
            "train_acc": round(train_acc * 100, 2),
            "val_loss": round(val_loss, 4),
            "val_acc": round(val_acc * 100, 2)
        })

        if val_loss < best_val_loss:
            best_val_loss = val_loss
            torch.save(model.state_dict(), CHECKPOINT_PATH)

        if epoch % 5 == 0 or epoch == epochs:
            print(f"Epoch [{epoch:02d}/{epochs:02d}] Train Loss: {train_loss:.4f}, Acc: {train_acc*100:.1f}% | Val Loss: {val_loss:.4f}, Acc: {val_acc*100:.1f}%")

    # Evaluation
    print(f"\nEvaluating on Independent Master Test Set ({len(y_test)} samples)...")
    best_weights = torch.load(CHECKPOINT_PATH, map_location=device, weights_only=True)
    model.load_state_dict(best_weights)
    model.eval()

    all_preds, all_targets = [], []
    with torch.no_grad():
        for bx, by in test_loader:
            bx = bx.to(device)
            logits, _ = model(bx)
            preds = torch.argmax(logits, dim=1).cpu().numpy()
            all_preds.extend(preds)
            all_targets.extend(by.numpy())

    all_preds = np.array(all_preds)
    all_targets = np.array(all_targets)

    acc = accuracy_score(all_targets, all_preds)
    prec = precision_score(all_targets, all_preds, zero_division=0)
    rec = recall_score(all_targets, all_preds, zero_division=0)
    f1 = f1_score(all_targets, all_preds, zero_division=0)
    tn, fp, fn, tp = confusion_matrix(all_targets, all_preds).ravel()

    print("\n" + "=" * 65)
    print("         MASTER HYBRID MODEL TEST EVALUATION")
    print("=" * 65)
    print(f"TEST ACCURACY:          {acc * 100:.2f}%")
    print(f"PRECISION:              {prec * 100:.2f}%")
    print(f"RECALL (SPOOF DET):     {rec * 100:.2f}%")
    print(f"F1-SCORE:               {f1 * 100:.2f}%")
    print(f"CONFUSION MATRIX:       TN={tn}, FP={fp}, FN={fn}, TP={tp}")
    print("=" * 65 + "\n")

    summary = {
        "dataset": "Master Hybrid (Kaggle DEEP-VOICE + Neural Vocoders + Replay)",
        "total_samples": len(y),
        "test_metrics": {
            "accuracy": round(acc * 100, 2),
            "precision": round(prec * 100, 2),
            "recall": round(rec * 100, 2),
            "f1_score": round(f1 * 100, 2),
            "confusion_matrix": {
                "true_negatives_real": int(tn),
                "false_positives": int(fp),
                "false_negatives": int(fn),
                "true_positives_fake": int(tp)
            }
        },
        "history": history
    }

    with open(METRICS_PATH, "w", encoding="utf-8") as f:
        import json
        json.dump(summary, f, indent=2)

    return summary


if __name__ == "__main__":
    train_hybrid_master(epochs=25, batch_size=32)
