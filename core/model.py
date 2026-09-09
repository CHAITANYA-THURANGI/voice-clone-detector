"""
Deep Learning Architecture: AcousticProsodicNet
Combines 1D Temporal Convolutions, Bidirectional Recurrent Units (BiGRU),
and Self-Attention Pooling for robust voice spoofing & cloning detection.
"""

import os
import torch
import torch.nn as nn
import torch.nn.functional as F
import numpy as np


class SelfAttentionPooling(nn.Module):
    """
    Self-Attention pooling mechanism.
    Learns to weigh anomalous/glitched frames higher than neutral/silent speech frames.
    """
    def __init__(self, input_dim: int):
        super(SelfAttentionPooling, self).__init__()
        self.attn_dense = nn.Linear(input_dim, 64)
        self.attn_vec = nn.Linear(64, 1, bias=False)

    def forward(self, x):
        # x shape: (batch_size, seq_len, input_dim)
        score = torch.tanh(self.attn_dense(x))         # (batch_size, seq_len, 64)
        weights = self.attn_vec(score)                 # (batch_size, seq_len, 1)
        weights = F.softmax(weights, dim=1)            # (batch_size, seq_len, 1)
        pooled = torch.sum(x * weights, dim=1)         # (batch_size, input_dim)
        return pooled, weights.squeeze(-1)


class AcousticProsodicNet(nn.Module):
    """
    Hybrid Deep Neural Network designed for CPU-efficient, high-precision voice clone detection.
    Integrates spectral transition features with prosodic contour evolution.
    """
    def __init__(self, input_dim: int = 32, hidden_dim: int = 64, num_classes: int = 2):
        super(AcousticProsodicNet, self).__init__()
        
        # 1D Temporal Convolutions for local acoustic-spectral dynamics
        self.conv1 = nn.Conv1d(in_channels=input_dim, out_channels=48, kernel_size=3, padding=1)
        self.bn1 = nn.BatchNorm1d(48)
        self.conv2 = nn.Conv1d(in_channels=48, out_channels=hidden_dim, kernel_size=3, padding=1)
        self.bn2 = nn.BatchNorm1d(hidden_dim)
        self.dropout_conv = nn.Dropout(0.2)

        # Bidirectional GRU for prosodic rhythm and temporal context
        self.gru = nn.GRU(
            input_size=hidden_dim,
            hidden_size=hidden_dim,
            num_layers=2,
            batch_first=True,
            bidirectional=True,
            dropout=0.2
        )

        # Attention pooling (input dim = hidden_dim * 2 due to bidirectional GRU)
        gru_out_dim = hidden_dim * 2
        self.attn_pool = SelfAttentionPooling(gru_out_dim)

        # Classification MLP
        self.layer_norm = nn.LayerNorm(gru_out_dim)
        self.fc1 = nn.Linear(gru_out_dim, 64)
        self.dropout_fc = nn.Dropout(0.3)
        self.fc2 = nn.Linear(64, num_classes)

    def forward(self, x):
        # x: (batch_size, seq_len, input_dim)
        # Transpose for Conv1D: (batch_size, input_dim, seq_len)
        x_conv = x.transpose(1, 2)
        h = F.gelu(self.bn1(self.conv1(x_conv)))
        h = F.gelu(self.bn2(self.conv2(h)))
        h = self.dropout_conv(h)

        # Transpose back for GRU: (batch_size, seq_len, hidden_dim)
        h_seq = h.transpose(1, 2)
        gru_out, _ = self.gru(h_seq)

        # Attention Pooling
        pooled, attn_weights = self.attn_pool(gru_out)

        # Classification Head
        normed = self.layer_norm(pooled)
        feat = F.gelu(self.fc1(normed))
        feat = self.dropout_fc(feat)
        logits = self.fc2(feat)

        return logits, attn_weights

    def predict_sample(self, feature_matrix: np.ndarray, device: str = "cpu") -> dict:
        """
        Runs single-sample inference on an extracted (100, 32) feature matrix.
        Returns:
            real_prob: float (0.0 to 1.0)
            fake_prob: float (0.0 to 1.0)
            prediction: 'REAL' or 'FAKE'
            confidence: float (0.0 to 100.0)
        """
        self.eval()
        with torch.no_grad():
            tensor = torch.from_numpy(feature_matrix).unsqueeze(0).float().to(device)
            logits, attn = self(tensor)
            probs = F.softmax(logits, dim=1).cpu().numpy()[0]
            real_prob = float(probs[0])
            fake_prob = float(probs[1])

            pred = "FAKE" if fake_prob >= 0.50 else "REAL"
            conf = max(real_prob, fake_prob) * 100.0

            return {
                "prediction": pred,
                "real_probability": round(real_prob, 4),
                "fake_probability": round(fake_prob, 4),
                "confidence": round(conf, 2),
                "attention_weights": attn.cpu().numpy()[0].tolist()
            }


def load_trained_model(checkpoint_path: str = "models/acoustic_prosodic_net.pth", device: str = "cpu"):
    """Instantiates and loads model weights from checkpoint if available."""
    if os.path.exists(checkpoint_path):
        try:
            state_dict = torch.load(checkpoint_path, map_location=device, weights_only=True)
            # If checkpoint has conformer keys, instantiate EnterpriseVoiceConformer
            if any("conformer" in k or "asp" in k for k in state_dict.keys()):
                from core.conformer_model import load_enterprise_conformer
                return load_enterprise_conformer(checkpoint_path, device=device)
            
            model = AcousticProsodicNet(input_dim=32, hidden_dim=64, num_classes=2)
            model.load_state_dict(state_dict)
            model.to(device)
            model.eval()
            return model
        except Exception:
            pass

    model = AcousticProsodicNet(input_dim=32, hidden_dim=64, num_classes=2)
    model.to(device)
    model.eval()
    return model

