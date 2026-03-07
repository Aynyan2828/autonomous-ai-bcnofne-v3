# autonomous AI BCNOFNe system v3 (shipOS) - ROADMAP

本システムは今回（MVP）にてマイクロサービスアーキテクチャの骨組み、各種安全装置、およびLINE等を通した会話基盤を構築しました。
今後は以下のロードマップに沿って拡張を行っていく予定です。

## Phase 5: Voice & Hardware Integration (近い将来)
- **Voice Engine 統合**: `voice-router` スタブを実際のナースロボタイプT (HTTP GET/POST API) および OpenAI TTS API と結合し、実際に音声ファイルを出力・再生できるようにする。
- **GPIO / 物理キー対応**: F13〜F22キーの検知スクリプト（Python `evdev` または GPIOライブラリ等）を作成し、`core` 内部の各種イベント（音声モード切替、ストップなど）へ直結する。
- **OLED / ファン制御**: 過去バージョン(v2)等で利用していた `OLEDFanController` をホストOS側、もしくは `gui` の裏で動く専用コンテナとして統合し、`SystemState` の変更をOLEDにリアルタイム反映する。

## Phase 6: Autonomous Automation & Playwright 実装
- **高度なPlaywrightエージェント**: `browser-agent` において、`playwright` を使って実際にブラウザを非同期起動し、DOM解析結果を `core` にフィードバックして自律的にページを遷移・スクレイピングするループを実装。
- **LLM関数呼び出し (Function Calling)**: `core` の自然言語処理部分を拡張し、OpenAIのFunction Calling機能を使って、「NASのファイルを整理して」「システムをスキャンして」といった自然言語の指示から直接 `storage-manager` や `watchdog` を呼び出す機構を入れる。

## Phase 7: Storage Expansion & Self-Healing
- **Samba / Tailscale の高度連携**: NAS機能として、Tailscaleを通じた外部からのファイルやり取りトリガー機能の作成。
- **Log -> Action の自己修復**: `watchdog` がただエラーを検知するだけでなく、過去の `diary_entries` や `memory` から「このエラーの時はコンテナ再起動で直った」という履歴を引き出し、自動的に復旧スクリプトを走らせる完全なSelf-Healingシステムを構築。

## Phase 8: Long-Term Memory & Proactive Assistance
- **ベクトルデータベース化**: 現在は単純なテキストとしてSQLiteに保存している `Memory` を、ChromaDB等のベクトルストアに移行し、AIが過去数年分の会話履歴から有益な情報を検索できるようにする。
- **真の能動的支援**: ユーザーがLINEで話しかけなくても、CPU温度が高ければ「マスター、ちょっとRaspberryPiが熱いばい！ファン全開にするね！」などの完全能動型の会話を開始する（※課金に配慮しつつ）。
