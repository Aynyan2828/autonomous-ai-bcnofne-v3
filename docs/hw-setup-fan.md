# BCNOFNe v3 HW Setup: PWM Fan Control

このドキュメントでは、Raspberry Pi 4B に 4ピンPWMファンを接続し、`oled-controller` から制御するための設定手順を説明します。
This document explains the setup procedure for connecting a 4-pin PWM fan to Raspberry Pi 4B and controlling it from `oled-controller`.

---

## 1. Hardware Connection / ハードウェア結線

| Pin (BCM) | Function | Color (Typical) |
|-----------|----------|-----------------|
| GPIO 18   | PWM Control | Blue / Green (PWM) |
| GPIO 24   | RPM (Tach) | Yellow / White (TACH) |
| 5V / 12V  | Power | Red |
| GND       | Ground | Black |

> [!IMPORTANT]
> 12Vファンを使用する場合は、別途電源を用意し、GNDのみを共通にしてください。GPIO直結はしないでください。
> If using a 12V fan, provide external power and common GND only. Do not connect directly to GPIO.

---

## 2. Host OS Setup / ホストOS側の設定

`pigpio` をコンテナ内から使用するため、ホストOSで `pigpiod` デーモンを起動しておく必要があります。
To use `pigpio` from within the container, you need to run the `pigpiod` daemon on the host OS.

```bash
# Install pigpio
sudo apt update
sudo apt install pigpio

# Enable and start pigpiod
sudo systemctl enable pigpiod
sudo systemctl start pigpiod
```

---

## 3. Deployment / 展開

`docker-compose.yml` において、`oled-controller` がホストのネットワークまたは特定のIPを通じて `pigpiod` にアクセスできる必要があります。現在の実装ではデフォルトの `pigpio.pi()` (localhost) を試行します。

---

## 4. Systemd Service Example / Systemd サービス例

`pigpiod` が確実に先に起動し、その後に Docker コンテナ（BCNOFNe）が起動するように順序を制御することを推奨します。

### /etc/systemd/system/pigpiod.service.d/override.conf (推奨)
```ini
[Service]
ExecStart=
ExecStart=/usr/bin/pigpiod -g
```
> [!NOTE]
> デフォルトの `-l` オプションがあると Docker コンテナから接続できません。コンテナ外（ホスト）からの接続を許可するために `-l` は外してください。

### BCNOFNe サービス全体の起動例
```ini
[Unit]
Description=BCNOFNe system services
After=docker.service pigpiod.service
Requires=docker.service pigpiod.service

[Service]
Type=oneshot
RemainAfterExit=yes
WorkingDirectory=/home/pi/autonomous-ai-bcnofne-v3
ExecStart=/bin/bash start.sh
ExecStop=/usr/bin/docker compose down

[Install]
WantedBy=multi-user.target
```

---

## 5. Testing / テスト方法

`oled-controller` のログを確認し、RPMが取得できているか確認してください。
Check the `oled-controller` logs to verify RPM measurement.

```bash
docker compose logs -f oled-controller
```

OLEDに `FAN: 30% RPM: 1200` のように表示されれば成功です。
If OLED displays `FAN: 30% RPM: 1200`, the setup is successful.

---

## 6. Future Extensions / 将来の拡張案

- **High-temp Alert**: CPU温度が75度を超えた場合に、LINEへ緊急通知を送る。
- **Fan Failure Detection**: Dutyが30%以上なのに RPMが0の場合、ファン故障または異物混入としてAIが警告を出す。
- **Voyage Log Integration**: 航海日誌に「本日は高温により最大出力で航行した」といった記録を自動挿入する。
