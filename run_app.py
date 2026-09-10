"""
Single-Command Launcher for VoiceShield AI.
Starts FastAPI backend server and serves the Interactive Cyber-Defense Dashboard.
"""

import os
import sys
import uvicorn

PROJECT_ROOT = os.path.dirname(os.path.abspath(__file__))
if PROJECT_ROOT not in sys.path:
    sys.path.insert(0, PROJECT_ROOT)

from data.dataset_builder import generate_benchmark_audio_files
from train_scratch import train_model_from_scratch, CHECKPOINT_PATH


def main():
    print("=" * 80)
    print("   VOICESHIELD AI - REAL-TIME VOICE CLONE DETECTION & PREVENTION (SIH PS-26104)")
    print("=" * 80)

    # 1. Ensure benchmark audio files exist
    samples_dir = os.path.join(PROJECT_ROOT, "data", "samples")
    if not os.path.exists(samples_dir) or len(os.listdir(samples_dir)) == 0:
        print("[INIT] Generating benchmark sample audios...")
        generate_benchmark_audio_files()

    # 2. Ensure model checkpoint exists
    if not os.path.exists(CHECKPOINT_PATH):
        print("[INIT] Model checkpoint not found. Training AcousticProsodicNet from scratch...")
        train_model_from_scratch(epochs=18, batch_size=16)

    import socket

    def get_local_ip():
        try:
            s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
            s.connect(("8.8.8.8", 80))
            ip = s.getsockname()[0]
            s.close()
            return ip
        except Exception:
            return "127.0.0.1"

    local_ip = get_local_ip()
    host = os.environ.get("HOST", "0.0.0.0")
    port = int(os.environ.get("PORT", 8000))

    print(f"\n🚀 System Online & Operational!")
    print(f"👉 Local Web Dashboard:       http://localhost:{port}")
    print(f"📱 Mobile / Network Dashboard: http://{local_ip}:{port}")
    print(f"📖 OpenAPI Swagger Docs:      http://localhost:{port}/docs")
    print(f"🔒 DPDP Act 2023 Compliance:  ACTIVE (Zero-retention ephemeral memory)")
    print("=" * 80 + "\n")

    uvicorn.run("api.server:app", host=host, port=port, log_level="info")


if __name__ == "__main__":
    main()
