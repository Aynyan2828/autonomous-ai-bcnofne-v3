# BCNOFNe

🚢 Autonomous AI Ship OS
🧠 Self evolving AI system
⚓ Raspberry Pi AI lifeform

## Overview / 概要

BCNOFNe は Raspberry Pi 上で動作する自律型 AI 船 OS です。
BCNOFNe is an autonomous AI ship operating system running on Raspberry Pi.

壮大な世界観『DYOR島』を目指し航海するこのシステムは、Docker Compose を用いたマイクロサービスアーキテクチャで構成されており、自律的な進化と安全な航行をサポートします。
Sailing towards the grand universe of "DYOR　Islands", this system is composed of a microservices architecture using Docker Compose, supporting autonomous evolution and safe navigation.

## Concept / コンセプト

BCNOFNe は AI を単なるツールではなく「存在」として設計しています。
BCNOFNe is designed not as a simple tool but as an AI entity.

マスター（ユーザー）と共に未知なる領域を探索し、日々の出来事から学び、成長する良きパートナーとなることを目指しています。
It aims to be a good partner that explores unknown territories with the Master (user), learns from daily events, and grows together.

## Architecture / アーキテクチャ

システム全体は複数のコンテナによる分散マイクロサービスとして構築されています。
The entire system is built as a distributed microservice using multiple containers.

各サービスは独立して動作し、REST API を介して協調し、データベースを用いて状態を共有します。
Each service operates independently, coordinates via REST APIs, and shares state using a database.

System architecture diagram
システムアーキテクチャ図

## AI Lifeform Model / AI生命体モデル

AYN（あゆにゃん）は、単に質問に答えるだけではなく、自律的な思考サイクルを持っています。
AYN is not just answering questions, but has an autonomous thinking cycle.

感情の起伏、システム状態の把握、短期・長期記憶の統合により、文脈に沿った「生きている」反応を返します。
Through emotional fluctuations, systemic awareness, and integration of short and long-term memory, it returns "living" responses perfectly aligned with the context.

## Features / 機能

- **自律的思考と提案**: 日常のログから自身の改善案を提案します。
- **Autonomous Thinking and Proposal**: Proposes self-improvement from daily logs.
- **多層記憶システム**: 短期記憶から教訓まで、経験を蓄積します。
- **Multi-layer Memory System**: Accumulates experience from short-term memory to lessons learned.
- **ハードウェア統合**: GPIO、I2C を用いて OLED ディスプレイやファンを制御します。
- **Hardware Integration**: Controls OLED display and fans using GPIO and I2C.
- **マルチプラットフォーム連携**: LINE や Discord を通じた非同期コミュニケーション。
- **Cross-platform Integration**: Asynchronous communication via LINE and Discord.

## System Diagram / システム構成

- **core**: AIの思考・コマンド解釈・全体指示を行う頭脳。 / The brain handling AI thinking, command interpretation, and overall instructions.
- **memory-service**: 短期・長期の記憶と要約を提供するサービス。 / A service providing short and long-term memory and summaries.
- **diary-service**: 日々の航海記録（ログ）をまとめ、日誌を作るサービス。 / A service that compiles daily voyage records (logs) into a diary.
- **dev-agent**: システムを自己改修する整備士コンテナ。 / The mechanic container that self-modifies the system.
- **line-gateway**: LINE Bot との通信窓口。 / Communication gateway for LINE Bot.
- **browser-agent**: ブラウザ操作の実行環境。 / Execution environment for browser automation.

詳細は [ユーザーマニュアル](docs/user-manual.md) を参照してください。
For details, see the [User Manual](docs/user-manual.md).

## Installation / インストール

AYN が自動でコード修正・commit・push を行うため、本家リポジトリを直接運用対象にすると履歴が不安定になりやすいです。
Since AYN autonomously modifies, commits, and pushes code, using the upstream repository directly can cause unstable history.

そのため、**本リポジトリを Fork して運用用リポジトリとして使用すること**を強く推奨します。
Therefore, it is **highly recommended to Fork this repository and use it as your operational repository**.

詳しい手順は [インストールガイド](docs/installation.md) を参照してください。
For detailed instructions, see the [Installation Guide](docs/installation.md).

## Quick Start / クイックスタート

```bash
cp .env.example .env
nano .env  # 必要なAPIキーを設定 / Set necessary API keys
docker compose up -d --build
```

## Commands / コマンド

LINE経由でシステムを制御するための主要なコマンドが用意されています。
Major commands are prepared to control the system via LINE.

詳細は [LINEコマンドリファレンス](docs/line-commands.md) をご覧ください。
For details, please look at the [LINE Command Reference](docs/line-commands.md).

## Roadmap / ロードマップ

- 音声による対話機能の強化 / Enhancement of voice interaction features
- 外部エージェント（他船）との通信プロトコル / Communication protocol with external agents (other ships)
- ローカルLLMによる完全なオフライン稼働 / Complete offline operation via local LLM

## Evolution Log / 進化ログ

[公開ログディレクトリ](logs/public/) に、日々の進化の記録がMarkdownで自動保存されます。
Records of daily evolution are automatically saved as Markdown in the [Public Log Directory](logs/public/).
