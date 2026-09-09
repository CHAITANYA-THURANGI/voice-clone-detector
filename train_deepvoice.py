"""
Training Engine for Kaggle DEEP-VOICE Dataset:
"Speech Dataset of Human and AI-Generated Voices"
(birdy654/deep-voice-deepfake-voice-recognition)

1. Extracts Real.zip and Fake.zip
2. Segments multi-minute recordings into 3-second active speech chunks using VAD
3. Extracts 32-dim temporal acoustic-prosodic feature matrices
4. Caches feature tensors to data/deepvoice_cached_features.npz
5. Trains AcousticProsodicNet from scratch with validation & test evaluation
6. Saves production weights to models/acoustic_prosodic_net.pth
"""

import os
import sys
import glob
import time
import zipfile
import numpy as np
import soundfile as sf
import torch
import torch.nn as nn
from torch.utils.data import TensorDataset, DataLoader
from sklearn.model_selection import train_test_split
from sklearn.metrics import accuracy_score, precision_score, recall_score, f1_score, confusion_matrix

PROJECT_ROOT = os.path.dirname(os.path.abspath(__file__))
if PROJECT_ROOT not in sys.path:
    sys.path.insert(0, PROJECT_ROOT)

from core.audio_processor import load_audio, voice_activity_filter
from core.feature_extraction import extract_temporal_feature_matrix
from core.model import AcousticProsodicNet


DATASET_DIR = os.path.join(PROJECT_ROOT, "datasets", "Speech Dataset of Human and AI-Generated Voices")
EXTRACT_DIR = os.path.join(PROJECT_ROOT, "datasets", "extracted")
REAL_ZIP = os.path.join(DATASET_DIR, "Real.zip")
FAKE_ZIP = os.path.join(DATASET_DIR, "Fake.zip")
CACHE_FILE = os.path.join(PROJECT_ROOT, "data", "deepvoice_cached_features.npz")
CHECKPOINT_PATH = os.path.join(PROJECT_ROOT, "models", "acoustic_prosodic_net.pth")
METRICS_PATH = os.path.join(PROJECT_ROOT, "models", "training_metrics.json")


def extract_zips_if_needed():
    os.makedirs(EXTRACT_DIR, exist_ok=True)
    real_out = os.path.join(EXTRACT_DIR, "Real")
    fake_out = os.path.join(EXTRACT_DIR, "Fake")

    if not os.path.exists(real_out) or len(os.listdir(real_out)) == 0:
        print(f"[1/4] Extracting Real.zip to {EXTRACT_DIR}...")
        with zipfile.ZipFile(REAL_ZIP, 'r') as z:
            z.extractall(EXTRACT_DIR)
        print("  Real.zip extraction complete.")
    else:
        print("  Real directory already extracted.")

    if not os.path.exists(fake_out) or len(os.listdir(fake_out)) == 0:
        print(f"[1/4] Extracting Fake.zip to {EXTRACT_DIR}...")
        with zipfile.ZipFile(FAKE_ZIP, 'r') as z:
            z.extractall(EXTRACT_DIR)
        print("  Fake.zip extraction complete.")
    else:
        print("  Fake directory already extracted.")

    return real_out, fake_out


def extract_chunks_from_recordings(
    folder_path: str,
    label: int,
    chunks_per_file: int = 35,
    chunk_sec: float = 3.0,
    sr: int = 16000
):
    """
    Reads multi-minute recordings, applies VAD, slices into chunk_sec speech windows,
    and extracts (100, 32) feature matrices.
    """
    wav_files = sorted(glob.glob(os.path.join(folder_path, "*.wav")))
    chunk_len = int(sr * chunk_sec)
    features_list = []
    labels_list = []

    class_name = "REAL" if label == 0 else "FAKE"
    print(f"  Processing {len(wav_files)} {class_name} recordings from {folder_path}...")

    for idx, fpath in enumerate(wav_files, start=1):
        try:
            fname = os.path.basename(fpath)
            # Load & normalize to 16kHz mono
            waveform = load_audio(fpath)
            # Filter silences so we extract rich phonetic content
            active_speech = voice_activity_filter(waveform, sr=sr)

            total_speech_len = len(active_speech)
            if total_speech_len < chunk_len:
                continue

            # Calculate slice indices
            max_possible_chunks = total_speech_len // chunk_len
            num_to_take = min(chunks_per_file, max_possible_chunks)

            # Distribute slices evenly across the recording
            step = max(chunk_len, (total_speech_len - chunk_len) // max(1, num_to_take - 1)) if num_to_take > 1 else chunk_len

            for c_i in range(num_to_take):
                start = c_i * step
                end = start + chunk_len
                if end > total_speech_len:
                    start = total_speech_len - chunk_len
                    end = total_speech_len

                chunk = active_speech[start:end]
                feat_matrix = extract_temporal_feature_matrix(chunk, sr=sr)
                features_list.append(feat_matrix)
                labels_list.append(label)

            if idx % 5 == 0 or idx == len(wav_files):
                print(f"    [{idx:02d}/{len(wav_files):02d}] {fname} -> {num_to_take} chunks extracted.")
        except Exception as e:
            print(f"    Error processing {fpath}: {e}")

    return features_list, labels_list


def prepare_and_cache_features(force_recompute: bool = False):
    if os.path.exists(CACHE_FILE) and not force_recompute:
        print(f"Loading pre-cached Kaggle DEEP-VOICE dataset from {CACHE_FILE}...")
        data = np.load(CACHE_FILE)
        return data["X"], data["y"]

    real_dir, fake_dir = extract_zips_if_needed()

    print("\n[2/4] Slicing recordings and extracting 32-dim Acoustic-Prosodic features...")
    real_feats, real_labels = extract_chunks_from_recordings(real_dir, label=0, chunks_per_file=35)
    fake_feats, fake_labels = extract_chunks_from_recordings(fake_dir, label=1, chunks_per_file=35)

    all_feats = real_feats + fake_feats
    all_labels = real_labels + fake_labels

    X = np.array(all_feats, dtype=np.float32)
    y = np.array(all_labels, dtype=np.int64)

    # Shuffle
    perm = np.random.permutation(len(y))
    X = X[perm]
    y = y[perm]

    os.makedirs(os.path.dirname(CACHE_FILE), exist_ok=True)
    np.savez_compressed(CACHE_FILE, X=X, y=y)
    print(f"\n[2/4] Dataset cached successfully to {CACHE_FILE}")
    print(f"      Total samples: {len(y)} (Real: {np.sum(y == 0)}, Fake: {np.sum(y == 1)})")
    print(f"      Tensor Shape:  {X.shape}")

    return X, y


def train_on_deepvoice(epochs: int = 22, batch_size: int = 32, lr: float = 1e-3):
    X, y = prepare_and_cache_features()

    device = "cuda" if torch.cuda.is_available() else "cpu"
    print("\n" + "=" * 80)
    print(f"🚀 TRAINING ACOUSTIC-PROSODIC NET FROM SCRATCH ON KAGGLE DEEP-VOICE DATASET")
    print(f"💻 Compute Device: {device.upper()}")
    if device == "cuda":
        print(f"🔥 GPU Acceleration: {torch.cuda.get_device_name(0)}")
        print(f"💾 VRAM: {torch.cuda.get_device_properties(0).total_memory / (1024**3):.1f} GB")
    print("=" * 80)

    # Stratified Train (70%), Val (15%), Test (15%)
    X_train, X_temp, y_train, y_temp = train_test_split(X, y, test_size=0.30, random_state=42, stratify=y)
    X_val, X_test, y_val, y_test = train_test_split(X_temp, y_temp, test_size=0.50, random_state=42, stratify=y_temp)

    print(f"Split sizes: Train={len(y_train)}, Val={len(y_val)}, Test={len(y_test)}")

    train_loader = DataLoader(TensorDataset(torch.from_numpy(X_train).float(), torch.from_numpy(y_train).long()), batch_size=batch_size, shuffle=True)
    val_loader = DataLoader(TensorDataset(torch.from_numpy(X_val).float(), torch.from_numpy(y_val).long()), batch_size=batch_size, shuffle=False)
    test_loader = DataLoader(TensorDataset(torch.from_numpy(X_test).float(), torch.from_numpy(y_test).long()), batch_size=batch_size, shuffle=False)

    model = AcousticProsodicNet(input_dim=32, hidden_dim=64, num_classes=2).to(device)
    criterion = nn.CrossEntropyLoss()
    optimizer = torch.optim.AdamW(model.parameters(), lr=lr, weight_decay=1e-4)
    scheduler = torch.optim.lr_scheduler.CosineAnnealingLR(optimizer, T_max=epochs)

    best_val_loss = float("inf")
    start_time = time.time()
    history = []

    print(f"\n[3/4] Running {epochs} training epochs...")
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

        if epoch % 2 == 0 or epoch == epochs:
            print(f"Epoch [{epoch:02d}/{epochs:02d}] Train Loss: {train_loss:.4f}, Acc: {train_acc*100:.1f}% | Val Loss: {val_loss:.4f}, Acc: {val_acc*100:.1f}%")

    duration = time.time() - start_time
    print(f"\nTraining completed in {duration:.2f} seconds.")
    print(f"Saved best model checkpoint to: {CHECKPOINT_PATH}")

    # [4/4] Test set evaluation
    print(f"\n[4/4] Evaluating on Independent Held-Out Test Set ({len(y_test)} samples)...")
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
    far = fp / (fp + tn + 1e-8)
    frr = fn / (fn + tp + 1e-8)

    print("\n" + "=" * 65)
    print("         FINAL BENCHMARK TEST RESULTS (KAGGLE DEEP-VOICE)")
    print("=" * 65)
    print(f"TEST ACCURACY:          {acc * 100:.2f}%")
    print(f"PRECISION:              {prec * 100:.2f}%")
    print(f"RECALL (SPOOF ATTACK):  {rec * 100:.2f}%")
    print(f"F1-SCORE:               {f1 * 100:.2f}%")
    print(f"FALSE ALARM RATE (FAR): {far * 100:.2f}%")
    print(f"MISS RATE (FRR):        {frr * 100:.2f}%")
    print(f"CONFUSION MATRIX:       TN={tn}, FP={fp}, FN={fn}, TP={tp}")
    print("=" * 65 + "\n")

    summary = {
        "dataset": "Kaggle DEEP-VOICE: DeepFake Voice Recognition",
        "total_samples": len(y),
        "device": device,
        "training_duration_sec": round(duration, 2),
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
        import json
        json.dump(summary, f, indent=2)

    return summary


if __name__ == "__main__":
    train_on_deepvoice(epochs=22, batch_size=32)
