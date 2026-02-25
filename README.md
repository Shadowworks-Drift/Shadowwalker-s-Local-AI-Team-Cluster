# 🌑 Shadowwalker's Local AI Team Cluster

> *"Built in the dark. Runs in the dark. Occasionally catches fire in the dark."*

[![Status](https://img.shields.io/badge/status-Phase%205%20gloriously%20unstable-red)]()
[![Hardware](https://img.shields.io/badge/GPU-RTX%204090%2024GB-76b900)]()
[![OS](https://img.shields.io/badge/OS-Pop!__OS-48B9C7)]()
[![Vibe](https://img.shields.io/badge/vibe-grey%20hat%20chaos-black)]()

---

## What Is This?

A grey hat systems architect's attempt to build a **fully local, multi-agent AI team** capable of replacing expensive API calls with raw local compute. No cloud. No subscriptions. No apologies.

This repo documents the **real-time construction** of a local LLM mesh running:
- 🧠 **DeepSeek-R1 32B** — the reasoning brain
- ⚡ **Qwen2.5-Coder 32B** — the fast hands
- 🔧 **CrewAI** — the orchestration layer
- 🖥️ **Ollama** — the inference backbone
- 🎨 **ComfyUI integration** — because of course

Multi-agent. Locally sovereign. Architecturally unhinged.

---

## Hardware

| Component | Spec |
|---|---|
| GPU | NVIDIA RTX 4090 24GB |
| RAM | 64GB |
| Overflow | 140GB SSD Pagefile |
| OS | Pop!_OS (Ubuntu-based) |
| Attitude | Nonlinear |

---

## Architecture (Current Thinking)

```
[Supervisor]     deepseek-r1:32b   — plans, decomposes, decides
[Architect]      deepseek-r1:32b   — system design, deep reasoning  
[Coder]          qwen2.5-coder:32b — implementation, fast loop
[Critic]         qwen2.5-coder:32b — review, edge cases, refactor
[Memory]         ChromaDB          — shared persistent context
[Job Queue]      SQLite            — bridges agents ↔ ComfyUI nodes
```

Two-lane design — fast VRAM lane for execution, slow reasoning lane for architecture. Both local. Both free at point of use.

---

## Build Status

| Phase | Status | Notes |
|---|---|---|
| Phase 0 — System Prep | 🔄 In Progress | Pop!_OS + CUDA + Docker |
| Phase 1 — Ollama Setup | ⏳ Pending | Fast lane models first |
| Phase 2 — Open-WebUI | ⏳ Pending | Docker deployment |
| Phase 3 — Python Env | ⏳ Pending | CrewAI + LangChain |
| Phase 4 — Agent Mesh | ⏳ Pending | First multi-agent run |
| Phase 5 — ComfyUI Nodes | ⏳ Pending | AgentMesh node set |

*This table will probably lie to you. Check commits for ground truth.*

---

## Philosophy

This isn't a polished product. It's a **living build log** from someone who thinks topologically, works in recursive cycles, and has zero interest in doing things the conventional way.

Expect:
- Radical mid-build refactors
- Unconventional architectural decisions that make sense at 2am
- Occasional bursts of something that might be brilliance
- Honest documentation of what broke and why

Don't expect:
- Stability guarantees
- Conventional best practices (we know them — we just disagree)
- Apologies

---

## Related Projects

This cluster is part of a wider ecosystem:

- 🔐 **[CryptoNoise KSampler](https://github.com/)** — cryptographic art signing for ComfyUI
- 🌀 **Kotodama Systems** — quantum-inspired visual authentication
- 🧬 **Eidolon Drift** — consciousness as entropy optimization (yes, really)

---

## Getting Started

Full setup guide in [`SETUP.md`](./SETUP.md) — covers everything from bare metal to first multi-agent run.

> **Warning:** The setup guide assumes you know what you're doing. It also assumes you don't mind when things go sideways. Both assumptions are load-bearing.

---

## Contributing

Found a better way to do something? Pull request it. Disagree with an architectural decision? Open an issue and make your case. This is a thinking system — it benefits from adversarial input.

---

## License

MIT — take what's useful, leave what isn't, credit where it matters.

---

*Built by Shadowwalker. Fuelled by curiosity, tai chi, and the audacity to think local compute can go toe-to-toe with frontier models.*
