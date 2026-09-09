"""
Universal Custom Dataset Ingestion & Model Training Engine.
Allows training AcousticProsodicNet from scratch using ANY external audio dataset
(e.g., ASVspoof, InTheWild, LibriSpeech, WaveFake, or local real/fake folders).
Supports automatic GPU (CUDA RTX 4060) and CPU acceleration.
"""

import os
import sys
import glob
import time
import json
import numpy as np
import torch
import torch.nn as nn
from torch.utils.data import TensorDataset, DataLoader
from sklearn.model_selection import train_test_split
from sklearn.metrics import accuracy_score, precision_score, recall_score, f1_score, confusion_matrix

# Ensure project root is on sys.path
PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if PROJECT_ROOT not in sys.path:
    sys.path.insert(0, PROJECT_ROOT)

from core.audio_processor import load_audio, voice_activity_filter
from core.feature_extraction import extract_temporal_feature_matrix
from core.model import AcousticProsodicNet


def ingest_and_train_from_folders(
    real_dir: str = "audio_samples/real",
    fake_dir: str = "audio_samples/fake",
    checkpoint_out: str = "models/acoustic_prosodic_net.pth",
    epochs: int = 25,
    batch_size: int = 32,
    lr: float = 1e-3,
    max_samples_per_class: int = 2000
) -> dict:
    device = "cuda" if torch.cuda.is_available() else "cpu"
    print("=" * 80)
    print(f"🚀 INGESTING CUSTOM DATASET & TRAINING FROM SCRATCH")
    print(f"💻 Device Selected: {device.upper()}")
    if device == "cuda":
        print(f"🔥 GPU Acceleration: {torch.cuda.get_device_name(0)}")
        print(f"💾 Dedicated VRAM: {torch.cuda.get_device_properties(0).total_memory / (1024**3):.1f} GB")
    else:
        print("ℹ️ Note: Running on CPU. (To enable RTX 4060 GPU, install PyTorch with CUDA).")
    print("=" * 80)

    audio_extensions = ("*.wav", "*.mp3", "*.ogg", "*.flac", "*.m4a", "*.webm")

    # 1. Collect files
    real_files = []
    fake_files = []
    for ext in audio_extensions:
        real_files.extend(glob.glob(os.path.join(real_dir, ext)))
        real_files.extend(glob.glob(os.path.join(real_dir, "**", ext)))
        fake_files.extend(glob.glob(os.path.join(fake_dir, ext)))
        fake_files.extend(glob.glob(os.path.join(fake_dir, "**", ext)))

    real_files = sorted(list(set(real_files)))[:max_samples_per_class]
    fake_files = sorted(list(set(fake_files)))[:max_samples_per_class]

    print(f"Found {len(real_files)} Real audio files in {real_dir}")
    print(f"Found {len(fake_files)} Fake/Cloned audio files in {fake_dir}")

    if len(real_files) == 0 or len(fake_files) == 0:
        raise ValueError(
            f"Insufficient samples. Place your .wav/.ogg files in '{real_dir}' and '{fake_dir}', "
            "or use the built-in online generator."
        )

    # 2. Extract Features
    X_list = []
    y_list = []

    print("\n[1/3] Extracting 32-dim Acoustic-Prosodic feature sequences...")
    for idx, fpath in enumerate(real_files):
        try:
            wav = load_audio(fpath)
            wav = voice_activity_filter(wav)
            feat = extract_temporal_feature_matrix(wav)
            X_list.append(feat)
            y_list.append(0)  # 0 = REAL
        except Exception as e:
            print(f"Warning: skipped {fpath}: {e}")

    for idx, fpath in enumerate(fake_files):
        try:
            wav = load_audio(fpath)
            wav = voice_activity_filter(wav)
            feat = extract_temporal_feature_matrix(wav)
            X_list.append(feat)
            y_list.append(1)  # 1 = FAKE
        except Exception as e:
            print(f"Warning: skipped {fpath}: {e}")

    X = np.array(X_list, dtype=np.float32)
    y = np.array(y_list, dtype=np.int64)

    # Shuffle
    perm = np.random.permutation(len(y))
    X, y = X[perm], y[perm]

    print(f"\n[2/3] Feature extraction complete: {len(y)} samples, Shape: {X.shape}")

    # Split
    X_train, X_temp, y_train, y_temp = train_test_split(X, y, test_size=0.30, random_state=42, stratify=y)
    X_val, X_test, y_val, y_test = train_test_split(X_temp, y_temp, test_size=0.50, random_state=42, stratify=y_temp)

    train_loader = DataLoader(TensorDataset(torch.from_numpy(X_train).float(), torch.from_numpy(y_train).long()), batch_size=batch_size, shuffle=True)
    val_loader = DataLoader(TensorDataset(torch.from_numpy(X_val).float(), torch.from_numpy(y_val).long()), batch_size=batch_size, shuffle=False)
    test_loader = DataLoader(TensorDataset(torch.from_numpy(X_test).float(), torch.from_numpy(y_test).long()), batch_size=batch_size, shuffle=False)

    # 3. Model Training
    print(f"\n[3/3] Training AcousticProsodicNet on {device.upper()} for {epochs} epochs...")
    model = AcousticProsodicNet(input_dim=32, hidden_dim=64, num_classes=2).to(device)
    criterion = nn.CrossEntropyLoss()
    optimizer = torch.optim.AdamW(model.parameters(), lr=lr, weight_decay=1e-4)
    scheduler = torch.optim.lr_scheduler.CosineAnnealingLR(optimizer, T_max=epochs)

    best_val_loss = float("inf")
    start_time = time.time()

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

        if val_loss < best_val_loss:
            best_val_loss = val_loss
            os.makedirs(os.path.dirname(checkpoint_out) or ".", exist_ok=True)
            torch.save(model.state_dict(), checkpoint_out)

        if epoch % 5 == 0 or epoch == epochs:
            print(f"Epoch [{epoch:02d}/{epochs:02d}] Train Loss: {train_loss:.4f}, Acc: {train_acc*100:.1f}% | Val Loss: {val_loss:.4f}, Acc: {val_acc*100:.1f}%")

    print(f"\nTraining completed in {time.time() - start_time:.2f}s.")

    # 4. Final Test Set Evaluation
    best_state = torch.load(checkpoint_out, map_location=device, weights_only=True)
    model.load_state_dict(best_state)
    model.eval()

    all_preds = []
    all_targets = []
    with torch.no_grad():
        for bx, by in test_loader:
            bx = bx.to(device)
            logits, _ = model(bx)
            preds = torch.argmax(logits, dim=1).cpu().numpy()
            all_preds.extend(preds)
            all_targets.extend(by.numpy())

    acc = accuracy_score(all_targets, all_preds)
    prec = precision_score(all_targets, all_preds, zero_division=0)
    rec = recall_score(all_targets, all_preds, zero_division=0)
    f1 = f1_score(all_targets, all_preds, zero_division=0)
    tn, fp, fn, tp = confusion_matrix(all_targets, all_preds).ravel()

    print("\n" + "=" * 50)
    print("       TEST EVALUATION METRICS (CUSTOM DATASET)")
    print("=" * 50)
    print(f"ACCURACY:  {acc * 100:.2f}%")
    print(f"PRECISION: {prec * 100:.2f}%")
    print(f"RECALL:    {rec * 100:.2f}%")
    print(f"F1-SCORE:  {f1 * 100:.2f}%")
    print(f"CONFUSION MATRIX: TN={tn}, FP={fp}, FN={fn}, TP={tp}")
    print("=" * 50 + "\n")

    return {
        "device": device,
        "accuracy": round(acc * 100, 2),
        "precision": round(prec * 100, 2),
        "recall": round(rec * 100, 2),
        "f1_score": round(f1 * 100, 2)
    }


if __name__ == "__main__":
    real_path = sys.argv[1] if len(sys.argv) > 1 else "audio_samples/real"
    fake_path = sys.argv[2] if len(sys.argv) > 2 else "audio_samples/fake"
    ingest_and_train_from_folders(real_dir=real_path, fake_dir=fake_path)
