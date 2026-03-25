# プロンプトカタログ (Prompt Catalog)

BCNOFNe v3.3.1 で使用される主要なプロンプトの定義一覧です。

| タスク ID | 役割 | 入力変数 | 出力形式 |
| :--- | :--- | :--- | :--- |
| `chat` | ユーザーとの対話 | `history`, `input` | Text (博多弁) |
| `summary` | 短いテキストの要約 | `input_text` | JSON (summary, keywords, importance) |
| `chunk_summary` | 長文分割時の断片要約 | `input_text` | JSON (chunk_summary, keywords) |
| `final_summary` | 断片を統合した最終要約 | `input_text` | JSON (final_summary, keywords, importance) |
| `classification` | 出来事のレイヤー分類 | `input_text` | JSON (primary_label, confidence, reason) |
| `notification` | 通知文の生成 | `event_detail` | JSON (title, body, priority) |
| `code` | 自律開発でのコード生成 | `file_path`, `plan`, `base_code` | Text (Raw Code) |
| `repair` | JSON 構造の修復 | `input_text` | JSON (valid JSON object) |
| `proactive` | AYN の独り言・思考 | `context` | Text (思考ログ) |
| `observation` | システム異常の観測分析 | `logs`, `metrics` | JSON (candidates, urgency) |

## 配置ルール
- プロンプト定義: `prompts/manifest.yaml`
- システムプロンプト本文: `prompts/system/*.txt`
- ユーザープロンプト本文: `prompts/user/*.txt`
- Few-shot 例示: `prompts/fewshot/*.json`
