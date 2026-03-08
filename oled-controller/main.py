import os
import sys
import time
import asyncio
import psutil
from fastapi import FastAPI, Depends
from sqlalchemy.orm import Session
from contextlib import asynccontextmanager

sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from shared.database import SessionLocal
from shared.models import SystemState, ShipMode

# OLED & Fan dependencies
try:
    import RPi.GPIO as GPIO
    import board
    import busio
    import adafruit_ssd1306
    from PIL import Image, ImageDraw, ImageFont
    HARDWARE_AVAILABLE = True
except Exception as e:
    import traceback
    HARDWARE_AVAILABLE = False
    print(f"[OLED/FAN] Hardware libraries not available. Running in stub mode. ({e})")
    traceback.print_exc()

app = FastAPI(title="shipOS OLED & Fan Controller")

# Configuration Constants
OLED_WIDTH = 128
OLED_HEIGHT = 64
FAN_PIN = 14
TEMP_THRESHOLD_HIGH = 60.0 # Fan ON
TEMP_THRESHOLD_LOW = 45.0  # Fan OFF

# shipOS モード表示マッピング（航海用語）
SHIP_MODE_DISPLAY = {
    "autonomous":  "SAIL",    # 自律航海
    "user_first":  "PORT",    # 入港待機
    "maintenance": "DOCK",    # ドック入り
    "power_save":  "ANCHOR",  # 停泊
    "safe":        "SOS",     # 救難信号
}

SHIP_MODE_EMOJI = {
    "autonomous":  "⛵",
    "user_first":  "🏠",
    "maintenance": "🔧",
    "power_save":  "🌙",
    "safe":        "🆘",
}

# AI状態 → 航海用語
AI_STATE_DISPLAY = {
    "Idle":          "WATCH",    # 見張り
    "Planning":      "HELM",     # 操舵中
    "Acting":        "ENGINE",   # 機関稼働
    "Moving Files":  "CARGO",    # 積荷移動
    "Error":         "ALARM",    # 警報
    "Wait":          "SIGNAL",   # 信号待ち
    "RUNNING":       "HELM",
    "STOPPED":       "ALARM",
}

# Runtime Variables
fan_is_on = False
oled_display = None
scroll_message = ""
scroll_pos = OLED_WIDTH
last_touch_ts = time.time()

def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()

def setup_hardware():
    global oled_display, fan_is_on
    if not HARDWARE_AVAILABLE:
        return

    # Fan Setup
    GPIO.setmode(GPIO.BCM)
    GPIO.setup(FAN_PIN, GPIO.OUT)
    GPIO.output(FAN_PIN, GPIO.LOW)
    fan_is_on = False

    # OLED Setup
    try:
        i2c = busio.I2C(board.SCL, board.SDA)
        oled_display = adafruit_ssd1306.SSD1306_I2C(OLED_WIDTH, OLED_HEIGHT, i2c, addr=0x3C)
        oled_display.fill(0)
        oled_display.show()
    except Exception as e:
        print(f"Failed to initialize OLED: {e}")
        oled_display = None

def get_cpu_temp():
    try:
        with open("/sys/class/thermal/thermal_zone0/temp", "r") as f:
            temp = int(f.read()) / 1000.0
            return temp
    except:
        return 0.0

def control_fan(temp):
    global fan_is_on
    if not HARDWARE_AVAILABLE:
        return

    if temp > TEMP_THRESHOLD_HIGH and not fan_is_on:
        GPIO.output(FAN_PIN, GPIO.HIGH)
        fan_is_on = True
    elif temp < TEMP_THRESHOLD_LOW and fan_is_on:
        GPIO.output(FAN_PIN, GPIO.LOW)
        fan_is_on = False

def get_system_state_val(db: Session, key: str, default: str) -> str:
    state = db.query(SystemState).filter_by(key=key).first()
    return state.value if state else default

def compute_mood(temp: float, ai_status: str, ship_mode: str) -> tuple[int, str]:
    """旧バージョンの簡易版Mood算出 (OLED表示用)"""
    score = 80
    
    # 温度による減点
    if temp >= 75:
        score -= 35
    elif temp >= 65:
        score -= 20
    elif 0 < temp <= 45:
        score += 5
        
    # AI状態補正
    st = (ai_status or "").lower()
    if "error" in st or "stop" in st or ship_mode == "safe":
        score -= 25
    elif "wait" in st:
        score -= 8
    elif "run" in st:
        score += 2

    score = max(0, min(100, int(round(score))))
    
    if score >= 85: emoji = "😎"
    elif score >= 70: emoji = "😊"
    elif score >= 55: emoji = "😗"
    elif score >= 35: emoji = "😨"
    else: emoji = "🥵" if temp >= 70 else "😤"
        
    return score, emoji

def update_oled(db: Session):
    global scroll_pos, scroll_message
    if not HARDWARE_AVAILABLE or not oled_display:
        return

    # データの取得
    ai_status = get_system_state_val(db, "ai_status", "RUNNING")
    ship_mode = get_system_state_val(db, "ship_mode", "autonomous") # 内部名は小文字のautonomous等になった
    temp = get_cpu_temp()
    
    # Mood算出
    score, mood_emoji = compute_mood(temp, ai_status, ship_mode)
    
    # 表示マッピング
    mode_disp = SHIP_MODE_DISPLAY.get(ship_mode, "SAIL")
    mode_emoji = SHIP_MODE_EMOJI.get(ship_mode, "⛵")
    ai_disp = AI_STATE_DISPLAY.get(ai_status, ai_status[:6])
    
    # ネットワーク情報はMVPでは環境変数やダミーでしのぐ
    ip = os.environ.get("HOST_IP", "192.168.x.x") 
    
    # スクロールメッセージ設定
    new_scroll = get_system_state_val(db, "oled_scroll_msg", "System Online")
    if new_scroll != scroll_message:
        scroll_message = new_scroll
        scroll_pos = OLED_WIDTH

    image = Image.new("1", (OLED_WIDTH, OLED_HEIGHT))
    draw = ImageDraw.Draw(image)
    
    try:
        # 日本語や絵文字も表示できるフォントが必要だが、コンテナ内にはデフォしかない可能性が高い。
        # ひとまずデフォルトで表示を試みるが、絵文字は文字化けする可能性があるため、フォールバックも考慮。
        font = ImageFont.load_default()
    except:
        font = None # Use basic text
        
    # ====== DRAWING ======
    # 行1: タイトルと船・モード (shipOS: SAIL ⛵)
    draw.text((0, 0), f"shipOS:{mode_disp} {mode_emoji}", font=font, fill=255)
    
    # 行2: DEST (V3ではとりあえず固定かSystemStateから取得)
    goal = get_system_state_val(db, "ai_target_goal", "---")[:13]
    draw.text((0, 12), f"DEST:{goal}", font=font, fill=255)
    
    # 行3: HELM (HELM:WATCH 😊85)
    draw.text((0, 24), f"HELM:{ai_disp} {mood_emoji}{score:02d}", font=font, fill=255)
    
    # 行4: 温度等ハードウェア (TEMP:45.0C DISK:...)
    fan_mark = "*" if fan_is_on else " "
    draw.text((0, 36), f"T:{temp:.1f}C FAN[{fan_mark}]", font=font, fill=255)
    
    # 行5: IP (IP:192.168.x.x)
    draw.text((0, 48), f"IP:{ip}", font=font, fill=255)
    
    # スクロール位置更新
    scroll_pos -= 2
    # 文字列の長さ * ピクセル(約6px)
    max_len = len(scroll_message) * 6
    if scroll_pos < -max_len:
        scroll_pos = OLED_WIDTH
        
    oled_display.image(image)
    oled_display.show()

async def hardware_loop():
    setup_hardware()
    
    db = SessionLocal()
    try:
        while True:
            temp = get_cpu_temp()
            control_fan(temp)
            update_oled(db)
            db.commit() # Fresh read next time
            await asyncio.sleep(0.1) # 10FPS程度のスクロールを維持
    except Exception as e:
        print(f"Hardware loop error: {e}")
    finally:
        db.close()
        if HARDWARE_AVAILABLE:
            GPIO.cleanup()

@asynccontextmanager
async def lifespan(app: FastAPI):
    task = asyncio.create_task(hardware_loop())
    yield
    task.cancel()
    if HARDWARE_AVAILABLE:
        GPIO.cleanup()
        if oled_display:
            oled_display.fill(0)
            oled_display.show()

app.router.lifespan_context = lifespan

@app.get("/health")
def health_check():
    return {
        "status": "ok",
        "service": "oled-controller",
        "hardware_present": HARDWARE_AVAILABLE,
        "fan_on": fan_is_on,
        "cpu_temp": get_cpu_temp()
    }
