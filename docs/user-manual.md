# User Manual / 完全取扱説明書

## System Overview / システム概要

BCNOFNe system (shipOS) の構成は複数の独立したサービスから成り立っています。
The structure of BCNOFNe system (shipOS) consists of multiple independent services.

*   **core**
    AI の思考、コマンド解釈、全体指示を行う頭脳です。
    The brain that handles AI thinking, command interpretation, and overall instructions.
*   **memory-service**
    短期・長期の記憶と要約を提供するサービスです。
    A service that provides short-term and long-term memory and summaries.
*   **diary-service**
    日々の航海記録（ログ）をまとめ、日誌を作るサービスです。
    A service that compiles daily voyage records (logs) into a diary.
*   **dev-agent**
    システムを自己分析し、改修案を提案・実行する自律型整備士コンテナです。
    An autonomous mechanic container that analyzes the system, proposes, and executes modifications.
*   **line-gateway**
    ユーザーとの主な通信窓口となる LINE Bot 環境です。
    The LINE Bot environment serving as the primary communication gateway with the user.
*   **browser-agent**
    Playwright などを用いて、UIを通じたブラウザ操作を実行する環境です。
    An execution environment for browser operations through UI using tools like Playwright.

---

## AI Lifeform Behaviour / AI生命体の振る舞い

AI は以下のサイクルで行動し、成長します。
The AI acts and grows through the following cycles.

1.  **observe** (観測する)
    システム状態、ログ、ユーザーからのメッセージを読み取ります。
    Reads system states, logs, and messages from the user.
2.  **interpret** (解釈する)
    観測した情報を現在の自分の状態や記憶と照らし合わせて意味を理解します。
    Understands the meaning of observed information against its current state and memories.
3.  **store memory** (記憶を保存する)
    重要だと判断した出来事を、短期記憶 (WORKING/EPISODIC) として保存します。
    Saves events deemed important as short-term memory (WORKING/EPISODIC).
4.  **update internal state** (内部状態を更新する)
    出来事の結果として、AI の感情や状態 (CALM, FOCUSED など) を変化させます。
    Changes the AI's emotions and states (CALM, FOCUSED, etc.) as a result of events.
5.  **generate goals** (目標を生成する)
    現在の状態に基づき、その日に達成したい目標やタスクを自身で設定します。
    Sets goals and tasks to achieve that day on its own based on the current state.
6.  **act** (行動する)
    目標達成に向けて、システムの制御、提案、またはユーザーへのメッセージ送信を行います。
    Controls the system, proposes actions, or sends messages to the user to achieve goals.
7.  **reflect** (振り返る)
    一定期間（1日など）の終わりに、蓄積した短期記憶を要約し、より高次な「教訓」を導き出します。
    At the end of a certain period (e.g., a day), summarizes accumulated short-term memories to derive higher-order "lessons".
8.  **evolve** (進化する)
    教訓をもとに、dev-agent がソースコードの改修案を作成し、システムの能力をアップデートします。
    Based on the lessons, the dev-agent creates source code modification proposals to update the system's capabilities.

---

## Internal State / AI内部状態

AYN は自身の状態を以下のカテゴリで表現します。
AYN expresses its state in the following categories.

*   **CALM** (穏やか)
    通常稼働時やエラーがない、落ち着いた状態です。
    A calm state without errors during normal operation.
*   **FOCUSED** (集中)
    何かのタスクや分析、目標に向かって真剣に取り組んでいる状態です。
    A state seriously tackling tasks, analysis, or goals.
*   **CURIOUS** (好奇心)
    新しい情報や未知のデータを見つけ、もっと知りたいと感じている状態です。
    A state finding new information or unknown data, feeling wanting to know more.
*   **TIRED** (疲れ)
    CPU 負荷が高い、エラーが多いなど、システムが疲労を感じている状態です。
    A state where the system feels fatigued, such as high CPU load or many errors.
*   **STORM** (嵐)
    重大なエラーが続発したり、システムが危機的な状況にある荒れた状態です。
    A rough state with consecutive critical errors or the system in a critical situation.
*   **RELIEVED** (安堵)
    エラーや問題を乗り越え、安心した状態です。
    A relieved state after overcoming errors or problems.
*   **PROUD** (誇り)
    目標を達成したり、進化に成功して自信に満ちている状態です。
    A state full of confidence upon achieving a goal or successful evolution.
