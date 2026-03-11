# autonomous AI BCNOFNe system v3 (shipOS) - ROADMAP / ロードマップ

本システムは今回（MVP）にてマイクロサービスアーキテクチャの骨組み、各種安全装置、およびLINE等を通した会話基盤を構築しました。
This system has built the skeleton of the microservices architecture, various safety devices, and the conversation foundation via LINE etc. in this MVP.

今後は以下のロードマップに沿って拡張を行っていく予定です。
From now on, we plan to expand according to the following roadmap.

## Phase 5: Voice & Hardware Integration (近い将来 / Near Future)

- **Voice Engine 統合 / Voice Engine Integration**: 
`voice-router` スタブを実際のナースロボタイプT (HTTP GET/POST API) および OpenAI TTS API と結合し、実際に音声ファイルを出力・再生できるようにする。
Integrate the `voice-router` stub with the actual Nurse Robot Type T (HTTP GET/POST API) and OpenAI TTS API to actually output and play voice files.

- **GPIO / 物理キー対応 / GPIO & Physical Key Support**: 
F13〜F22キーの検知スクリプト（Python `evdev` または GPIOライブラリ等）を作成し、`core` 内部の各種イベント（音声モード切替、ストップなど）へ直結する。
Create a detection script for the F13-F22 keys (using Python `evdev` or GPIO libraries, etc.) and connect it directly to various internal events in `core` (voice mode switching, stop, etc.).

- **OLED / ファン制御 / OLED & Fan Control**: 
過去バージョン(v2)等で利用していた `OLEDFanController` をホストOS側、もしくは `gui` の裏で動く専用コンテナとして統合し、`SystemState` の変更をOLEDにリアルタイム反映する。
Integrate the `OLEDFanController` used in past versions (v2) either on the host OS side or as a dedicated container running behind `gui`, and reflect `SystemState` changes to the OLED in real-time.

## Phase 6: Autonomous Automation & Playwright 実装 / Implementation

- **高度なPlaywrightエージェント / Advanced Playwright Agent**: 
`browser-agent` において、`playwright` を使って実際にブラウザを非同期起動し、DOM解析結果を `core` にフィードバックして自律的にページを遷移・スクレイピングするループを実装。
In the `browser-agent`, asynchronously load the browser using `playwright`, feedback the DOM analysis results to the `core`, and implement a loop to autonomously navigate and scrape pages.

- **LLM関数呼び出し (Function Calling) / LLM Function Calling**: 
`core` の自然言語処理部分を拡張し、OpenAIのFunction Calling機能を使って、「NASのファイルを整理して」「システムをスキャンして」といった自然言語の指示から直接 `storage-manager` や `watchdog` を呼び出す機構を入れる。
Expand the natural language processing part of `core` and use OpenAI's Function Calling feature to introduce a mechanism that directly calls `storage-manager` or `watchdog` from natural language instructions like "organize the NAS files" or "scan the system".

## Phase 7: Storage Expansion & Self-Healing / ストレージ拡張と自己修復

- **Samba / Tailscale の高度連携 / Advanced Integration of Samba & Tailscale**: 
NAS機能として、Tailscaleを通じた外部からのファイルやり取りトリガー機能の作成。
Create a trigger function for file exchange from the outside through Tailscale as a NAS feature.

- **Log -> Action の自己修復 / Self-Healing from Log to Action**: 
`watchdog` がただエラーを検知するだけでなく、過去の `diary_entries` や `memory` から「このエラーの時はコンテナ再起動で直った」という履歴を引き出し、自動的に復旧スクリプトを走らせる完全なSelf-Healingシステムを構築。
Construct a complete Self-Healing system where `watchdog` not only detects errors but also pulls history from past `diary_entries` or `memory` (e.g., "this error was fixed by restarting the container") and automatically runs recovery scripts.

## Phase 8: Long-Term Memory & Proactive Assistance / 長期記憶と能動的支援

- **ベクトルデータベース化 / Vector Database Conversion**: 
現在は単純なテキストとしてSQLiteに保存している `Memory` を、ChromaDB等のベクトルストアに移行し、AIが過去数年分の会話履歴から有益な情報を検索できるようにする。
Migrate the `Memory`, currently saved as simple text in SQLite, to a vector store such as ChromaDB, enabling the AI to search for useful information from conversational history spanning several years.

- **真の能動的支援 / True Proactive Assistance**: 
ユーザーがLINEで話しかけなくても、CPU温度が高ければ「マスター、ちょっとRaspberryPiが熱いばい！ファン全開にするね！」などの完全能動型の会話を開始する（※課金に配慮しつつ）。
Start fully proactive conversations (while being mindful of billing constraints) even when the user hasn't engaged via LINE, such as saying "Master, the Raspberry Pi is getting a bit hot! Turning the fan to full blast!".
