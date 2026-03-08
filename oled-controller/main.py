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

# Runtime Variables
fan_is_on = False
oled_display = None
scroll_message = ""
scroll_pos = OLED_WIDTH

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

def update_oled(db: Session):
    global scroll_pos, scroll_message
    if not HARDWARE_AVAILABLE or not oled_display:
        return

    # データの取得
    ai_status = get_system_state_val(db, "ai_status", "RUNNING")
    ship_mode = get_system_state_val(db, "ship_mode", "PORT")
    temp = get_cpu_temp()
    
    # 状況に応じた表情 (AIN)
    face = "(-_-)"  # PORT/待機
    if ship_mode == "SAIL":
        face = "(o_o)"  # 監視/稼働
    elif ai_status == "STOPPED" or ship_mode == "SOS":
        face = "(x_x)"  # エラー停止
    
    # スクロールメッセージ設定
    new_scroll = get_system_state_val(db, "oled_scroll_msg", "System Online")
    if new_scroll != scroll_message:
        scroll_message = new_scroll
        scroll_pos = OLED_WIDTH

    image = Image.new("1", (OLED_WIDTH, OLED_HEIGHT))
    draw = ImageDraw.Draw(image)
    
    try:
        font = ImageFont.load_default()
    except:
        font = None # Use basic text
        
    # ====== DRAWING ======
    # 行1: タイトルと船・モード
    draw.text((0, 0), f"shipOS: {ship_mode}", font=font, fill=255)
    
    # 行2: AIの顔と状態
    draw.text((0, 14), f"AI: {face} {ai_status}", font=font, fill=255)
    
    # 行3: 温度等ハードウェア
    fan_mark = "*" if fan_is_on else " "
    draw.text((0, 28), f"T:{temp:.1f}C FAN[{fan_mark}]", font=font, fill=255)
    
    # 行4: ネットワーク（コンテナ内なのでホストIPは限定的だが仮取得）
    # (ここではダミーや環境変数からとるのもあり)
    
    # 行5: スクロールメッセージ
    draw.text((scroll_pos, 48), scroll_message, font=font, fill=255)
    
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
