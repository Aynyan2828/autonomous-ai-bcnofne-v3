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
from shared.logger import ShipLogger

logger = ShipLogger("oled-controller")

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

def clean_text(text: str) -> str:
    """Keep printable characters including Japanese (UTF-8)."""
    if not text:
        return ""
    # ASCII 制御文字以外は大体許可する
    return "".join(c for c in text if ord(c) >= 32 or c == '\n')

app = FastAPI(title="shipOS OLED & Fan Controller")

# Configuration Constants
OLED_WIDTH = 128
OLED_HEIGHT = 64
FAN_PIN = 14
TEMP_THRESHOLD_HIGH = 60.0 # Fan ON
TEMP_THRESHOLD_LOW = 45.0  # Fan OFF

# shipOS Mode Mapping (Naval Terms)
SHIP_MODE_DISPLAY = {
    "autonomous":  "SAIL  >===>",
    "user_first":  "PORT  >===>",
    "maintenance": "DOCK  >===>",
    "power_save":  "ANCHOR>===>",
    "safe":        "SOS   >===>",
    "SAIL":        "SAIL  >===>",
    "PORT":        "PORT  >===>",
    "DOCK":        "DOCK  >===>",
    "ANCHOR":      "ANCHOR>===>",
    "SOS":         "SOS   >===>",
}

SHIP_MODE_EMOJI = {
    "autonomous":  "[~]",
    "user_first":  "[P]",
    "maintenance": "[M]",
    "power_save":  "[z]",
    "safe":        "[!]",
    "SAIL":        "[~]",
    "PORT":        "[P]",
    "DOCK":        "[M]",
    "ANCHOR":      "[z]",
    "SOS":         "[!]",
}

# AI State -> Faces
AI_STATE_FACE = {
    "Idle":          "(-_-)",
    "Planning":      "( ..)phi",
    "Acting":        "(o_o)",
    "Moving Files":  "( ..)phi",
    "Error":         "(x_x)",
    "Wait":          "(o_o)",
    "RUNNING":       "(o_o)",
    "STOPPED":       "(x_x)",
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

LOGO_PATH = "/app/oled_128x64_resize_dither.png"

def show_boot_animation():
    """Ship-like boot sequence animation with logo and progress bar."""
    if not HARDWARE_AVAILABLE or not oled_display:
        return
    
    # Load Logo
    logo = None
    paths_to_try = [LOGO_PATH, "oled_128x64_resize_dither.png", "./oled-controller/oled_128x64_resize_dither.png"]
    
    logger.info(f"OLED: Starting boot animation. Current DIR: {os.getcwd()}")
    logger.info(f"OLED: Files in /app: {os.listdir('/app') if os.path.exists('/app') else 'N/A'}")

    for p in paths_to_try:
        if os.path.exists(p):
            try:
                logo = Image.open(p).convert("1")
                logger.info(f"OLED: Successfully loaded logo from {p}")
                break
            except Exception as e:
                logger.error(f"OLED: Failed to open logo at {p}: {e}")
        else:
            logger.info(f"OLED: Logo not found at {p}")

    checks = [
        "CPU TEMPERATURE",
        "I2C BUS STATUS",
        "FAN CONTROLLER",
        "DATABASE CONN",
        "NETWORK CONFIG",
        "SHIPOS KERNEL "
    ]
    
    total_checks = len(checks)
    for i, label in enumerate(checks):
        if not oled_display:
            break
        
        # 起動イメージの作成
        if logo:
            image = logo.copy()
        else:
            image = Image.new("1", (OLED_WIDTH, OLED_HEIGHT))
            
        draw = ImageDraw.Draw(image)
        
        # テキストの視認性確保のために背景を少し黒く塗る
        draw.rectangle((0, 0, 110, 10), fill=0)
        draw.text((0, 0), "--- SYSTEM CHECK ---", font=ImageFont.load_default(), fill=255)
        
        # 最新のチェック項目を1つだけ出す（ロゴを隠しすぎないように）
        y_pos = 12
        draw.rectangle((0, y_pos, 120, y_pos + 9), fill=0)
        draw.text((0, y_pos), f"[ OK ] {checks[i]}", font=ImageFont.load_default(), fill=255)
            
        # プログレスバー（画面下部）
        bar_y = 54
        bar_h = 8
        draw.rectangle((0, bar_y, OLED_WIDTH - 1, bar_y + bar_h), outline=255, fill=0)
        progress_w = int((i + 1) / total_checks * (OLED_WIDTH - 4))
        draw.rectangle((2, bar_y + 2, 2 + progress_w, bar_y + bar_h - 2), fill=255)
        
        oled_display.image(image)
        oled_display.show()
        time.sleep(0.5)
    
    # Final ready message
    if oled_display:
        image = logo.copy() if logo else Image.new("1", (OLED_WIDTH, OLED_HEIGHT))
        draw = ImageDraw.Draw(image)
        draw.rectangle((10, 20, 118, 45), fill=0, outline=255)
        draw.text((15, 25), "ALL SYSTEMS GREEN", font=ImageFont.load_default(), fill=255)
        draw.text((15, 35), "    OUTWARD BOUND", font=ImageFont.load_default(), fill=255)
        oled_display.image(image)
        oled_display.show()
        time.sleep(1.5)

def show_shutdown_animation():
    """Ship-like shutdown sequence animation (Return to port)."""
    if not HARDWARE_AVAILABLE or not oled_display:
        return

    logo = None
    if os.path.exists(LOGO_PATH):
        try:
            logo = Image.open(LOGO_PATH).convert("1")
        except:
            pass

    # 1. 帰港メッセージを表示
    for i in range(6):
        image = logo.copy() if logo else Image.new("1", (OLED_WIDTH, OLED_HEIGHT))
        draw = ImageDraw.Draw(image)
        
        if i % 2 == 0:
            draw.rectangle((10, 20, 118, 45), fill=0, outline=255)
            draw.text((15, 25), " RETURN TO PORT ", font=ImageFont.load_default(), fill=255)
            draw.text((15, 35), " SHUTTING DOWN  ", font=ImageFont.load_default(), fill=255)
            
        oled_display.image(image)
        oled_display.show()
        time.sleep(0.5)

    # 2. フェードアウト（上下から収束）
    if logo:
        image = logo.copy()
        for y in range(0, OLED_HEIGHT // 2, 2):
            draw = ImageDraw.Draw(image)
            draw.line((0, y, OLED_WIDTH, y), fill=0)
            draw.line((0, OLED_HEIGHT - 1 - y, OLED_WIDTH, OLED_HEIGHT - 1 - y), fill=0)
            oled_display.image(image)
            oled_display.show()
            time.sleep(0.05)

    # 3. 最終メッセージ
    image = Image.new("1", (OLED_WIDTH, OLED_HEIGHT))
    draw = ImageDraw.Draw(image)
    draw.text((10, 20), "safe shutdown .", font=ImageFont.load_default(), fill=255)
    draw.text((10, 35), "see you master", font=ImageFont.load_default(), fill=255)
    oled_display.image(image)
    oled_display.show()
    time.sleep(2)

    oled_display.fill(0)
    oled_display.show()

def setup_hardware():
    global fan_is_on, oled_display
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
        # Start animation
        show_boot_animation()
    except Exception as e:
        logger.error(f"Failed to initialize OLED: {e}")
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
    """Simplified Mood calculation for OLED display (ASCII only)."""
    score = 80
    
    if temp >= 75:
        score -= 35
    elif temp >= 65:
        score -= 20
    elif 0 < temp <= 45:
        score += 5
        
    st = (ai_status or "").lower()
    if "error" in st or "stop" in st or ship_mode == "safe":
        score -= 25
    elif "wait" in st:
        score -= 8
    elif "run" in st:
        score += 2

    score = max(0, min(100, int(round(score))))
    
    if score >= 85: face = "(^o^)"
    elif score >= 70: face = "(^_^)"
    elif score >= 55: face = "(o_o)"
    elif score >= 35: face = "(._.)"
    else: face = "(x_x)" if temp >= 70 else "(>_<)"
        
    return score, face

def update_oled(db: Session):
    global scroll_pos, scroll_message
    if not HARDWARE_AVAILABLE or not oled_display:
        return

    # データの取得
    ai_status = get_system_state_val(db, "ai_status", "RUNNING")
    ship_mode = get_system_state_val(db, "ship_mode", "autonomous") # 内部名は小文字のautonomous等になった
    temp = get_cpu_temp()
    
    # Mood calculation
    score, _ = compute_mood(temp, ai_status, ship_mode)
    
    # Mapping
    mode_disp = SHIP_MODE_DISPLAY.get(ship_mode, "SAIL  >===>")
    mode_emoji = SHIP_MODE_EMOJI.get(ship_mode, "[~]")
    ai_face = AI_STATE_FACE.get(ai_status, "(-_-)")
    
    # Disk usage
    try:
        disk_pct = psutil.disk_usage('/').percent
    except:
        disk_pct = 0.0
    
    # Network info from environment
    ip = os.environ.get("HOST_IP", "??") 
    ts_ip = os.environ.get("TAILSCALE_IP", "??")
    
    # Webhook URL from DB (updated by start.sh)
    webhook_url = get_system_state_val(db, "last_webhook_url", "")
    webhook_part = f" WEBHOOK:{webhook_url}" if webhook_url else ""
    
    ip_scroll = f"LAN:{ip} TS:{ts_ip}{webhook_part}"
    
    # Scroll message setup (Clean ASCII only)
    new_scroll = clean_text(get_system_state_val(db, "oled_scroll_msg", "System Online"))
    total_scroll = f"{new_scroll} | {ip_scroll}"
    
    if total_scroll != scroll_message:
        scroll_message = total_scroll
        scroll_pos = OLED_WIDTH

    
    # Special faces mapping based on score
    if score < 40:
        ai_face = "(x_x)" 
    elif ai_status == "Planning":
        ai_face = "( ..)phi"
    elif ai_status == "RUNNING" or ai_status == "Acting":
        ai_face = "(o_o)"
    else:
        ai_face = "(-_-)"


    image = Image.new("1", (OLED_WIDTH, OLED_HEIGHT))
    draw = ImageDraw.Draw(image)
    
    try:
        # 日本語表示用のフォントをロード
        jp_font_paths = [
            "/usr/share/fonts/opentype/noto/NotoSansCJK-Regular.ttc",
            "/usr/share/fonts/truetype/noto/NotoSansCJK-Regular.ttc"
        ]
        font = None
        for p in jp_font_paths:
            if os.path.exists(p):
                font = ImageFont.truetype(p, 10)
                break
        if not font:
            font = ImageFont.load_default()
    except Exception as e:
        logger.error(f"Failed to load font: {e}")
        font = ImageFont.load_default()
        
    # ====== DRAWING ======
    # Line 1: shipOS: SAIL >===> [~]
    draw.text((0, 0), clean_text(f"shipOS:{mode_disp} {mode_emoji}"), font=font, fill=255)
    
    # Line 2: DEST: [Goal]
    # AI の最新の思考・活動ログを日本語で取得
    goal = get_system_state_val(db, "ai_target_goal", "---")
    # 日本語込みで13文字程度に制限（表示幅に合わせて調整が必要かもしれないが、まずはシンプルに）
    # スクロールさせることも検討できるが、一旦切り詰め
    goal_disp = clean_text(goal)[:20]
    draw.text((0, 11), f"DEST:{goal_disp}", font=font, fill=255)
    
    # Line 3: AI: (face)
    draw.text((0, 22), f"AI: {ai_face}", font=font, fill=255)
    
    # Line 4: Hardwares (TEMP/DISK)
    draw.text((0, 33), f"TEMP:{temp:.0f}C DISK:{disk_pct:.0f}%", font=font, fill=255)
    
    # Line 5: Blank or status (To keep spec alignment if needed, but moving IPs to scroll)
    draw.text((0, 44), "STATUS: ONLINE", font=font, fill=255)
    
    # Line 6: Scrolling message (Includes IPs)
    draw.text((scroll_pos, 55), scroll_message, font=font, fill=255)

    
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
    # Startup
    task = asyncio.create_task(hardware_loop())
    yield
    # Shutdown
    task.cancel()
    if HARDWARE_AVAILABLE:
        show_shutdown_animation()
        GPIO.cleanup()

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
