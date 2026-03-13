# Decploying to Walrus Site

Walrus Site は Sui ネットワーク上の分散型ストレージを使用した静的サイトホスティングサービスです。
作成した `/site` フォルダを以下の手順でデプロイできます。

## 📦 デプロイ手順

1.  **Walrus ツール (CLI) の準備**:
    - [Walrus CLI](https://github.com/MystenLabs/walrus-docs) がインストールされていることを確認してください。
2.  **サイトのパブリッシュ**:
    ターミナル（PowerShellなど）で以下のコマンドを実行します。
    ```bash
    walrus site publish ./site
    ```
    - このコマンドで `/site` フォルダ内のすべてのファイルが Walrus にアップロードされます。
3.  **URL の取得**:
    - コマンドが成功すると、オブジェクト ID と共に、サイトにアクセスするための URL（例: `https://[OBJECT_ID].walrus.site`）が表示されます。

## 📁 デプロイするフォルダ構成
```text
/site
├── index.html
├── lore.html
├── voyage-log.html
├── css/
│   └── style.css
└── assets/
    ├── ayn.png
    └── logo.png
```

## ⚠️ 注意事項
- このサイトは純粋な**静的 HTML** です。
- Sui ウォレットの残高（SUI または WAL）が、ストレージ料として必要になる場合があります。
