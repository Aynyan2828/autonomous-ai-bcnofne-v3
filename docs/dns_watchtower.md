# DNS Watchtower - AYN DNS Monitoring Integration

autonomous AI BCNOFNe system v3 (AYN) は、Raspberry Pi 上で動作する DNS 基盤を統合的に監視・要約する機能を持ってます。

## 全体構成

```mermaid
graph TD
    Internet((Internet))
    Master[マスター (LINE)]
    AYN[AYN (BCNOFNe v3)]
    
    subgraph "DNS Infrastructure"
        AGH[AdGuard Home]
        PH[Pi-hole]
        UB[Unbound]
    end
    
    AYN -- Monitoring (REST API) --> AGH
    AYN -- Monitoring (API) --> PH
    AYN -- Health Check (UDP) --> UB
    
    AGH -- Upstream --> UB
    PH -- Upstream --> UB
    UB -- Recursive Query --> Internet
    
    Master -- Command --> AYN
    AYN -- Summary/Report --> Master
```

## 各サービスの責務

- **AdGuard Home**: 主要な広告ブロック / クライアント管理
- **Pi-hole**: サブの広告ブロック / 統計（冗長化用）
- **Unbound**: 再帰リゾルバ（ローカルキャッシュとプライバシー保護）
- **AYN (BCNOFNe v3)**: 上記の稼働状況を監視し、AI が博多弁で要約報告を行う本体

## 53番ポート競合の考え方

Raspberry Pi 上で複数の DNS サービスを動かす場合、53番ポートは1つしか使えません。
推奨設定例:
- AdGuard Home: ポート 53 (標準)
- Pi-hole: ポート 5354 (別ポート)
- Unbound: ポート 5353 (アップストリーム用)

## LINE コマンド

- **「今日何した？」**: 日次活動要約に DNS ブロック数などが含まれます。
- **「DNS状況」**: 各サービスの稼働状態と最新の統計を表示します。
- **「AdGuard状態」 / 「Pi-hole状態」**: 各サービスの個別詳細状況を報告します。

## 障害時の挙動

どれか1つのサービスが止まっても、AYN 本体は停止しません。
日報に「取得失敗」として記録され、マスターに異常を報告します。
🚩
