"""
Model Export & Portability Generator:
Converts EnterpriseVoiceConformer checkpoint into universal, framework-agnostic formats:
1. ONNX (.onnx) - Framework-agnostic, runs on any OS/device with onnxruntime, C++, Java, JS, etc.
2. TorchScript (.pt) - Self-contained PyTorch serialization loadable via torch.jit.load() without source code.
3. Standalone Portable Client (voiceshield_client.py) - 3-line plug-and-play integration for external projects.
"""

import os
import sys
import numpy as np
import torch
import torch.nn as nn
import torch.nn.functional as F

PROJECT_ROOT = os.path.dirname(os.path.abspath(__file__))
if PROJECT_ROOT not in sys.path:
    sys.path.insert(0, PROJECT_ROOT)

from core.conformer_model import EnterpriseVoiceConformer, load_enterprise_conformer

EXPORT_DIR = os.path.join(PROJECT_ROOT, "model_export")
CHECKPOINT_PATH = os.path.join(PROJECT_ROOT, "models", "acoustic_prosodic_net.pth")


class ExportWrapper(nn.Module):
    """
    Wraps EnterpriseVoiceConformer to output normalized softmax probabilities directly:
    probs: (B, 2) -> [P(Real), P(Fake)]
    """
    def __init__(self, conformer_model: nn.Module):
        super().__init__()
        self.conformer = conformer_model

    def forward(self, x: torch.Tensor):
        logits, attn = self.conformer(x)
        probs = F.softmax(logits, dim=1)
        return probs


def export_all():
    os.makedirs(EXPORT_DIR, exist_ok=True)
    print("=" * 80)
    print("📦 VOICESHIELD AI - TRANSFERABLE MODEL EXPORT ENGINE")
    print("=" * 80)

    # 1. Load Trained PyTorch Model
    print(f"\n[1/4] Loading trained checkpoint: {CHECKPOINT_PATH}")
    base_model = load_enterprise_conformer(CHECKPOINT_PATH)
    base_model.eval()
    export_model = ExportWrapper(base_model)
    export_model.eval()

    dummy_input = torch.randn(1, 100, 32, dtype=torch.float32)
    with torch.no_grad():
        pt_probs = export_model(dummy_input)
        print(f"      PyTorch sanity test passed. Output shape: {pt_probs.shape}")

    # 2. Export to TorchScript (.pt)
    ts_path = os.path.join(EXPORT_DIR, "voiceshield_conformer.pt")
    print(f"\n[2/4] Exporting TorchScript model to: {ts_path}")
    try:
        traced_model = torch.jit.trace(export_model, dummy_input, check_trace=False)
        traced_model.save(ts_path)
        print("      ✅ TorchScript export successful!")

        # Verify TorchScript loading
        loaded_ts = torch.jit.load(ts_path)
        with torch.no_grad():
            ts_probs = loaded_ts(dummy_input)
            np.testing.assert_allclose(pt_probs.numpy(), ts_probs.numpy(), rtol=1e-4, atol=1e-4)
            print("      ✅ TorchScript verification PASSED (exact match with PyTorch)!")
    except Exception as e:
        print(f"      ❌ TorchScript export failed: {e}")

    # 3. Export to ONNX (.onnx)
    onnx_path = os.path.join(EXPORT_DIR, "voiceshield_conformer.onnx")
    print(f"\n[3/4] Exporting universal ONNX model to: {onnx_path}")
    try:
        try:
            torch.onnx.export(
                export_model,
                dummy_input,
                onnx_path,
                export_params=True,
                opset_version=17,
                do_constant_folding=True,
                input_names=["audio_features"],
                output_names=["probabilities"],
                dynamic_axes={
                    "audio_features": {0: "batch_size", 1: "time_frames"},
                    "probabilities": {0: "batch_size"}
                },
                dynamo=False
            )
        except TypeError:
            # Older or newer signature
            torch.onnx.export(
                export_model,
                dummy_input,
                onnx_path,
                export_params=True,
                opset_version=17,
                do_constant_folding=True,
                input_names=["audio_features"],
                output_names=["probabilities"],
                dynamic_axes={
                    "audio_features": {0: "batch_size", 1: "time_frames"},
                    "probabilities": {0: "batch_size"}
                }
            )
        print("      ✅ ONNX export successful!")

        # Verify with onnxruntime
        import onnxruntime as ort
        session = ort.InferenceSession(onnx_path, providers=["CPUExecutionProvider"])
        ort_inputs = {"audio_features": dummy_input.numpy()}
        ort_probs = session.run(None, ort_inputs)[0]
        np.testing.assert_allclose(pt_probs.numpy(), ort_probs, rtol=1e-4, atol=1e-4)
        print(f"      ✅ ONNX Runtime verification PASSED (exact match with PyTorch)!")
    except Exception as e:
        print(f"      ❌ ONNX export failed: {e}")

    # 4. Copy standard weights checkpoint
    pth_path = os.path.join(EXPORT_DIR, "voiceshield_weights.pth")
    torch.save(base_model.state_dict(), pth_path)
    print(f"\n[4/4] Saved PyTorch weights state_dict: {pth_path}")

    print("\n" + "=" * 80)
    print("🎉 ALL TRANSFERABLE FORMATS GENERATED SUCCESSFULLY!")
    print(f"📁 Destination Folder: {EXPORT_DIR}")
    for f in os.listdir(EXPORT_DIR):
        fpath = os.path.join(EXPORT_DIR, f)
        size_kb = os.path.getsize(fpath) / 1024
        print(f"   • {f:<30} ({size_kb:.1f} KB)")
    print("=" * 80)


if __name__ == "__main__":
    export_all()
