# 多層メモリモデル仕様 (7-Layer Memory Model)

BCNOFNe AYN の記憶システムは、人間の認知構造を模した 7 つのレイヤーで構成されます。

## 1. メモリレイヤー定義

| レイヤー | 名称 | 性質 | 保存先 | 保存期間 |
| :--- | :--- | :--- | :--- | :--- |
| `WORKING` | 作業メモリ | 現在の対話文脈、一時的なフラグ | SSD | 極短 (分) |
| `EPISODIC` | エピソード記憶 | 「いつ何が起きたか」のイベントログ | SSD | 短 (日) |
| `SEMANTIC` | 意味記憶 | 知識、仕様、一般常識、世界観 | SSD/HDD | 恒久 |
| `PROCEDURAL` | 手続き記憶 | スキル、手順、ツールの使い方 | SSD/HDD | 恒久 |
| `REFLECTIVE` | 内省記憶 | 反省点、学習結果、自己評価 | SSD/HDD | 長 (月) |
| `RELATIONAL` | 関係性記憶 | マスターの好み、過去の約束、親密度 | SSD/HDD | 恒久 |
| `MISSION` | 指揮記憶 | 中長期目標、未完了の重要タスク | SSD | 中 (週) |

## 2. 記憶のライフサイクル

### 2.1 生成と分類 (Classification)
- サービスが `POST /memories/` を呼び出した際、LLM が内容を分析し、最適な `layer` と `importance` (1-5) を自動判定する。

### 2.2 昇格 (Elevation)
- 同じトピックの `EPISODIC` 記憶が累積した場合、それらを統合して `SEMANTIC`（知識）や `REFLECTIVE`（反省）へ昇格させる。
- 重要度 (`importance`) が 4 以上の記憶は即座に長期記憶 (HDD) への複製対象となる。

### 2.3 圧縮と忘却 (Compression & Forgetting)
- `WORKING` メモリは対話終了後、または一定時間経過後に自動削除。
- 古い `EPISODIC` メモリ（7日以上経過）は要約され、HDD に移送された後、SSD からは削除される。

### 2.4 想起 (Recall)
- 想起要請があった場合、以下の重み付けで検索を行う：
    - **Relevance (関連性)**: ベクトル空間での距離（Semantic search）
    - **Recency (新近性)**: 時間経過による減衰
    - **Importance (重要性)**: `importance` カラムの値によるブースト
