"""
Training Engine: Train AcousticProsodicNet From Scratch.
Satisfies SIH Hackathon requirement to train a deep learning model from scratch
within CPU hardware limits and produce verified evaluation benchmarks.
"""

import os
import sys
import json
import time
import numpy as np
import torch
import torch.nn as nn
from torch.utils.data import TensorDataset, DataLoader
from sklearn.model_selection import train_test_split
from sklearn.metrics import classification_report, confusion_matrix, accuracy_score, precision_score, recall_score, f1_score

# Ensure root directory is on sys.path
PROJECT_ROOT = os.path.dirname(os.path.abspath(__file__))
if PROJECT_ROOT not in sys.path:
    sys.path.insert(0, PROJECT_ROOT)

from core.model import AcousticProsodicNet
from data.dataset_builder import build_and_cache_dataset, CACHE_FILE


MODELS_DIR = "models"
CHECKPOINT_PATH = os.path.join(MODELS_DIR, "acoustic_prosodic_net.pth")
METRICS_PATH = os.path.join(MODELS_DIR, "training_metrics.json")


def train_model_from_scratch(
    epochs: int = 18,
    batch_size: int = 16,
    lr: float = 1.2e-3,
    device: str = "cpu"
) -> dict:
    os.makedirs(MODELS_DIR, exist_ok=True)

    if not os.path.exists(CACHE_FILE):
        print("Cached features not found. Generating dataset now...")
        build_and_cache_dataset(num_samples_per_class=150)

    print(f"Loading cached dataset from {CACHE_FILE}...")
    data = np.load(CACHE_FILE)
    X = data["X"]
    y = data["y"]

    print(f"Total dataset size: {len(y)} samples (Real: {np.sum(y == 0)}, Fake: {np.sum(y == 1)})")

    # Stratified Train/Val/Test Split (70% Train, 15% Val, 15% Test)
    X_train, X_temp, y_train, y_temp = train_test_split(X, y, test_size=0.30, random_state=42, stratify=y)
    X_val, X_test, y_val, y_test = train_test_split(X_temp, y_temp, test_size=0.50, random_state=42, stratify=y_temp)

    print(f"Split sizes: Train={len(y_train)}, Val={len(y_val)}, Test={len(y_test)}")

    # PyTorch DataLoaders
    train_ds = TensorDataset(torch.from_numpy(X_train).float(), torch.from_numpy(y_train).long())
    val_ds = TensorDataset(torch.from_numpy(X_val).float(), torch.from_numpy(y_val).long())
    test_ds = TensorDataset(torch.from_numpy(X_test).float(), torch.from_numpy(y_test).long())

    train_loader = DataLoader(train_ds, batch_size=batch_size, shuffle=True)
    val_loader = DataLoader(val_ds, batch_size=batch_size, shuffle=False)
    test_loader = DataLoader(test_ds, batch_size=batch_size, shuffle=False)

    # Initialize model
    model = AcousticProsodicNet(input_dim=32, hidden_dim=64, num_classes=2).to(device)
    criterion = nn.CrossEntropyLoss()
    optimizer = torch.optim.AdamW(model.parameters(), lr=lr, weight_decay=1e-4)
    scheduler = torch.optim.lr_scheduler.CosineAnnealingLR(optimizer, T_max=epochs)

    best_val_loss = float("inf")
    history = []

    print("\nStarting Training from Scratch (AcousticProsodicNet)...")
    start_time = time.time()

    for epoch in range(1, epochs + 1):
        model.train()
        train_loss = 0.0
        train_correct = 0
        total_train = 0

        for batch_x, batch_y in train_loader:
            batch_x, batch_y = batch_x.to(device), batch_y.to(device)
            optimizer.zero_grad()
            logits, _ = model(batch_x)
            loss = criterion(logits, batch_y)
            loss.backward()
            nn.utils.clip_grad_norm_(model.parameters(), max_norm=1.0)
            optimizer.step()

            train_loss += loss.item() * len(batch_y)
            preds = torch.argmax(logits, dim=1)
            train_correct += (preds == batch_y).sum().item()
            total_train += len(batch_y)

        scheduler.step()
        train_loss /= total_train
        train_acc = train_correct / total_train

        # Validation
        model.eval()
        val_loss = 0.0
        val_correct = 0
        total_val = 0

        with torch.no_grad():
            for batch_x, batch_y in val_loader:
                batch_x, batch_y = batch_x.to(device), batch_y.to(device)
                logits, _ = model(batch_x)
                loss = criterion(logits, batch_y)

                val_loss += loss.item() * len(batch_y)
                preds = torch.argmax(logits, dim=1)
                val_correct += (preds == batch_y).sum().item()
                total_val += len(batch_y)

        val_loss /= total_val
        val_acc = val_correct / total_val

        history.append({
            "epoch": epoch,
            "train_loss": round(train_loss, 4),
            "train_acc": round(train_acc * 100, 2),
            "val_loss": round(val_loss, 4),
            "val_acc": round(val_acc * 100, 2)
        })

        if epoch % 2 == 0 or epoch == epochs:
            print(f"Epoch [{epoch:02d}/{epochs:02d}] "
                  f"Train Loss: {train_loss:.4f}, Train Acc: {train_acc*100:.1f}% | "
                  f"Val Loss: {val_loss:.4f}, Val Acc: {val_acc*100:.1f}%")

        # Save best model
        if val_loss < best_val_loss:
            best_val_loss = val_loss
            torch.save(model.state_dict(), CHECKPOINT_PATH)

    train_duration = time.time() - start_time
    print(f"\nTraining completed in {train_duration:.2f} seconds.")
    print(f"Saved best model checkpoint to: {CHECKPOINT_PATH}")

    # Final Evaluation on Held-Out Test Set
    print("\nEvaluating on Independent Test Set (45 samples)...")
    best_state = torch.load(CHECKPOINT_PATH, map_location=device, weights_only=True)
    model.load_state_dict(best_state)
    model.eval()

    all_preds = []
    all_targets = []

    with torch.no_grad():
        for batch_x, batch_y in test_loader:
            batch_x = batch_x.to(device)
            logits, _ = model(batch_x)
            preds = torch.argmax(logits, dim=1).cpu().numpy()
            all_preds.extend(preds)
            all_targets.extend(batch_y.numpy())

    all_preds = np.array(all_preds)
    all_targets = np.array(all_targets)

    acc = accuracy_score(all_targets, all_preds)
    prec = precision_score(all_targets, all_preds, zero_division=0)
    rec = recall_score(all_targets, all_preds, zero_division=0)
    f1 = f1_score(all_targets, all_preds, zero_division=0)

    # Confusion Matrix:
    # [ [True Negatives (TN), False Positives (FP)],
    #   [False Negatives (FN), True Positives (TP)] ]
    tn, fp, fn, tp = confusion_matrix(all_targets, all_preds).ravel()
    far = fp / (fp + tn + 1e-8)  # False Acceptance Rate (Real classified as Fake)
    frr = fn / (fn + tp + 1e-8)  # False Rejection Rate (Fake classified as Real)

    print("-" * 50)
    print(f"TEST ACCURACY:  {acc * 100:.2f}%")
    print(f"PRECISION:      {prec * 100:.2f}%")
    print(f"RECALL:         {rec * 100:.2f}%")
    print(f"F1-SCORE:       {f1 * 100:.2f}%")
    print(f"FALSE ALARM RATE (FAR): {far * 100:.2f}%")
    print(f"MISS RATE (FRR):        {frr * 100:.2f}%")
    print(f"CONFUSION MATRIX: TN={tn}, FP={fp}, FN={fn}, TP={tp}")
    print("-" * 50)

    results = {
        "architecture": "AcousticProsodicNet (1D-CNN + BiGRU + Self-Attention)",
        "training_duration_sec": round(train_duration, 2),
        "test_metrics": {
            "accuracy": round(acc * 100, 2),
            "precision": round(prec * 100, 2),
            "recall": round(rec * 100, 2),
            "f1_score": round(f1 * 100, 2),
            "far_percent": round(far * 100, 2),
            "frr_percent": round(frr * 100, 2),
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
        json.dump(results, f, indent=2)

    return results


if __name__ == "__main__":
    train_model_from_scratch(epochs=18, batch_size=16)
