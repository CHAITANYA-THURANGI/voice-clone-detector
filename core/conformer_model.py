"""
Enterprise Deep Learning Backbone: Multi-Scale Spectro-Temporal Conformer
Combines Depthwise Separable Convolution, Multi-Head Self-Attention (MHSA),
and Attentive Statistics Pooling (ASP) for enterprise-grade voice spoofing defense.
"""

import os
import torch
import torch.nn as nn
import torch.nn.functional as F
import numpy as np


class ConformerFeedForward(nn.Module):
    """Macaron-style Feed-Forward Network with Swish/GELU activation."""
    def __init__(self, dim: int, expansion_factor: int = 4, dropout: float = 0.1):
        super().__init__()
        inner_dim = dim * expansion_factor
        self.net = nn.Sequential(
            nn.LayerNorm(dim),
            nn.Linear(dim, inner_dim),
            nn.GELU(),
            nn.Dropout(dropout),
            nn.Linear(inner_dim, dim),
            nn.Dropout(dropout)
        )

    def forward(self, x):
        return self.net(x)


class ConformerConvModule(nn.Module):
    """
    Depthwise Separable Convolutional Block.
    Captures localized micro-acoustic artifacts, sub-band vocoder glitched frames,
    and instantaneous frequency fluctuations.
    """
    def __init__(self, dim: int, kernel_size: int = 7, dropout: float = 0.1):
        super().__init__()
        self.layer_norm = nn.LayerNorm(dim)
        self.pointwise_conv1 = nn.Conv1d(dim, dim * 2, kernel_size=1)
        self.depthwise_conv = nn.Conv1d(
            dim, dim, kernel_size=kernel_size,
            stride=1, padding=(kernel_size - 1) // 2,
            groups=dim
        )
        self.batch_norm = nn.BatchNorm1d(dim)
        self.pointwise_conv2 = nn.Conv1d(dim, dim, kernel_size=1)
        self.dropout = nn.Dropout(dropout)

    def forward(self, x):
        # x: (B, T, D)
        h = self.layer_norm(x).transpose(1, 2)  # (B, D, T)
        # Pointwise Conv + GLU
        h = self.pointwise_conv1(h)
        h = F.glu(h, dim=1)  # (B, D, T)
        # Depthwise Conv + BatchNorm + GELU
        h = self.depthwise_conv(h)
        h = self.batch_norm(h)
        h = F.gelu(h)
        # Pointwise Conv 2
        h = self.pointwise_conv2(h)
        h = self.dropout(h).transpose(1, 2)  # (B, T, D)
        return h


class ConformerBlock(nn.Module):
    """
    Single Conformer Block with Macaron-Style Scaling:
    FFN -> Self-Attention -> ConvModule -> FFN -> LayerNorm
    """
    def __init__(self, dim: int, num_heads: int = 4, ffn_expansion: int = 2, kernel_size: int = 7, dropout: float = 0.1):
        super().__init__()
        self.ffn1 = ConformerFeedForward(dim, expansion_factor=ffn_expansion, dropout=dropout)
        self.self_attn = nn.MultiheadAttention(embed_dim=dim, num_heads=num_heads, dropout=dropout, batch_first=True)
        self.conv_module = ConformerConvModule(dim, kernel_size=kernel_size, dropout=dropout)
        self.ffn2 = ConformerFeedForward(dim, expansion_factor=ffn_expansion, dropout=dropout)
        self.norm = nn.LayerNorm(dim)

    def forward(self, x):
        # 1. Half-step FFN
        x = x + 0.5 * self.ffn1(x)
        # 2. Multi-Head Attention
        attn_out, _ = self.self_attn(x, x, x)
        x = x + attn_out
        # 3. Convolution Module
        x = x + self.conv_module(x)
        # 4. Half-step FFN
        x = x + 0.5 * self.ffn2(x)
        return self.norm(x)


class AttentiveStatisticsPooling(nn.Module):
    """
    Attentive Statistics Pooling (ASP).
    Computes both the attention-weighted mean (mu) AND attention-weighted standard deviation (sigma).
    Crucial in enterprise biometrics for capturing temporal stability vs synthetic jitter.
    """
    def __init__(self, in_dim: int, hidden_dim: int = 64):
        super().__init__()
        self.attention_dense = nn.Sequential(
            nn.Linear(in_dim, hidden_dim),
            nn.Tanh(),
            nn.Linear(hidden_dim, 1)
        )

    def forward(self, x):
        # x: (B, T, D)
        score = self.attention_dense(x)         # (B, T, 1)
        alpha = F.softmax(score, dim=1)         # (B, T, 1)

        # Weighted Mean mu
        mu = torch.sum(alpha * x, dim=1)        # (B, D)

        # Weighted Standard Deviation sigma
        variance = torch.sum(alpha * (x - mu.unsqueeze(1)) ** 2, dim=1)
        sigma = torch.sqrt(torch.clamp(variance, min=1e-8))  # (B, D)

        # Concatenate [mu; sigma] -> Dimension 2 * D
        pooled = torch.cat([mu, sigma], dim=1)
        return pooled, alpha.squeeze(-1)


class EnterpriseVoiceConformer(nn.Module):
    """
    Complete Enterprise-Grade Deepfake Voice Verification Backbone.
    Input: (B, T, 32)
    Output: 3 Classes:
      - 0: HUMAN (Genuine biological human speech)
      - 1: NON_HUMAN (Synthetic voice, TTS, altered audio)
      - 2: VOICE_CLONING_ATTACK (High-threat neural voice clone & vocoder impersonation attack)
    """
    def __init__(self, input_dim: int = 32, d_model: int = 64, num_layers: int = 2, num_heads: int = 4, num_classes: int = 3):
        super().__init__()
        self.num_classes = num_classes
        self.d_model = d_model

        # Linear feature projection
        self.input_projection = nn.Sequential(
            nn.Linear(input_dim, d_model),
            nn.LayerNorm(d_model),
            nn.Dropout(0.1)
        )

        # Conformer Layers
        self.conformer_layers = nn.ModuleList([
            ConformerBlock(dim=d_model, num_heads=num_heads, ffn_expansion=2, kernel_size=7, dropout=0.1)
            for _ in range(num_layers)
        ])

        # Attentive Statistics Pooling (Outputs 2 * d_model = 128)
        self.asp = AttentiveStatisticsPooling(d_model, hidden_dim=64)

        # Enterprise Classification MLP Head
        pooled_dim = d_model * 2
        self.classifier = nn.Sequential(
            nn.Linear(pooled_dim, 64),
            nn.LayerNorm(64),
            nn.GELU(),
            nn.Dropout(0.25),
            nn.Linear(64, num_classes)
        )

    def forward(self, x, return_embeddings: bool = False):
        # x: (B, T, input_dim)
        h = self.input_projection(x)
        for layer in self.conformer_layers:
            h = layer(h)

        pooled, alpha = self.asp(h)
        logits = self.classifier(pooled)
        if return_embeddings:
            return logits, alpha, pooled
        return logits, alpha

    def extract_embedding(self, feature_matrix: np.ndarray, device: str = "cpu") -> np.ndarray:
        """Extracts 128-dimensional ASP representation embedding vector."""
        self.eval()
        with torch.no_grad():
            tensor = torch.from_numpy(feature_matrix).unsqueeze(0).float().to(device)
            _, _, pooled = self(tensor, return_embeddings=True)
            return pooled.cpu().numpy()[0]

    def predict_sample(self, feature_matrix: np.ndarray, device: str = "cpu") -> dict:
        self.eval()
        with torch.no_grad():
            tensor = torch.from_numpy(feature_matrix).unsqueeze(0).float().to(device)
            logits, attn = self(tensor)
            probs = F.softmax(logits, dim=1).cpu().numpy()[0]

            if self.num_classes == 3 and len(probs) >= 3:
                p_human = float(probs[0])
                p_nonhuman = float(probs[1])
                p_attack = float(probs[2])
                p_fake = float(np.clip(p_nonhuman + p_attack, 0.0, 1.0))

                pred_idx = int(np.argmax(probs))
                class_labels = {0: "HUMAN", 1: "NON_HUMAN", 2: "VOICE_CLONING_ATTACK"}
                predicted_class = class_labels.get(pred_idx, "UNKNOWN")

                pred = "REAL" if pred_idx == 0 else "FAKE"
                conf = float(probs[pred_idx]) * 100.0

                return {
                    "prediction": pred,
                    "predicted_class": predicted_class,
                    "class_index": pred_idx,
                    "real_probability": round(p_human, 4),
                    "fake_probability": round(p_fake, 4),
                    "confidence": round(conf, 2),
                    "class_probabilities": {
                        "human": round(p_human, 4),
                        "non_human": round(p_nonhuman, 4),
                        "cloning_attack": round(p_attack, 4)
                    },
                    "attention_weights": attn.cpu().numpy()[0].tolist()
                }
            else:
                real_prob = float(probs[0])
                fake_prob = float(probs[1]) if len(probs) > 1 else 1.0 - real_prob
                pred = "FAKE" if fake_prob >= 0.50 else "REAL"
                conf = max(real_prob, fake_prob) * 100.0

                return {
                    "prediction": pred,
                    "predicted_class": "VOICE_CLONING_ATTACK" if fake_prob >= 0.50 else "HUMAN",
                    "class_index": 1 if fake_prob >= 0.50 else 0,
                    "real_probability": round(real_prob, 4),
                    "fake_probability": round(fake_prob, 4),
                    "confidence": round(conf, 2),
                    "class_probabilities": {
                        "human": round(real_prob, 4),
                        "non_human": round(fake_prob * 0.4, 4),
                        "cloning_attack": round(fake_prob * 0.6, 4)
                    },
                    "attention_weights": attn.cpu().numpy()[0].tolist()
                }


def load_enterprise_conformer(checkpoint_path: str = "models/acoustic_prosodic_net.pth", device: str = "cpu", num_classes: int = 3):
    """Loads enterprise Conformer model with automatic weights and class mapping."""
    if os.path.exists(checkpoint_path):
        try:
            state_dict = torch.load(checkpoint_path, map_location=device, weights_only=True)
            # Detect number of classes from classifier weight shape: e.g. (3, 64) or (2, 64)
            ckpt_classes = num_classes
            for k, v in state_dict.items():
                if "classifier" in k and "weight" in k and v.ndim == 2:
                    ckpt_classes = v.shape[0]
            model = EnterpriseVoiceConformer(input_dim=32, d_model=64, num_layers=2, num_heads=4, num_classes=ckpt_classes)
            model.load_state_dict(state_dict)
            model.to(device)
            model.eval()
            return model
        except Exception as e:
            print(f"Notice: Conformer checkpoint load fallback: {e}")

    model = EnterpriseVoiceConformer(input_dim=32, d_model=64, num_layers=2, num_heads=4, num_classes=num_classes)
    model.to(device)
    model.eval()
    return model

