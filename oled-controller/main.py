import os
import sys
import time
import asyncio
import psutil
from fastapi import FastAPI, Depends
from sqlalchemy.orm import Session
from contextlib import asynccontextmanager

sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from shared import init_db
from shared.database import SessionLocal
from shared.models import SystemState, ShipMode, InternalStateHistory
from shared.logger import ShipLogger

# データベース初期化
init_db()

logger = ShipLogger("oled-controller")

# OLED & Fan dependencies
try:
    import pigpio
    from .fan_controller import FanController
    import board
    import busio
    import adafruit_ssd1306
    from PIL import Image, ImageDraw, ImageFont
    HARDWARE_AVAILABLE = True
except ImportError:
    # Try absolute import for local testing or different path structures
    try:
        import pigpio
        from fan_controller import FanController
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
except Exception as e:
    HARDWARE_AVAILABLE = False
    print(f"[OLED/FAN] Hardware error. ({e})")

def clean_text(text: str) -> str:
    """Keep printable characters including Japanese (UTF-8)."""
    if not text:
        return ""
    # ASCII 制御文字以外は大体許可する
    return "".join(c for c in text if ord(c) >= 32 or c == '\n')

app = FastAPI(title="BCNOFNe OLED & Fan Controller")

# Configuration Constants
OLED_WIDTH = 128
OLED_HEIGHT = 64
FAN_PWM_PIN = 18
FAN_TACH_PIN = 24
TEMP_THRESHOLD_HIGH = 60.0 # 100% Duty
TEMP_THRESHOLD_LOW = 40.0  # 30% Duty

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

INTERNAL_STATE_FACE = {
    "CALM": "(^-^)",
    "STORM": "(>_<)",
    "TIRED": "(=_=)",
    "FOCUSED": "(*_*)",
    "CURIOUS": "(O_O)",
    "RELIEVED": "(^o^)",
    "PROUD": "(`_`)"
}

# Runtime Variables
fan_ctrl = None
pi = None
fan_status = {"duty": 0, "rpm": 0}
oled_display = None
scroll_message = ""
scroll_pos = OLED_WIDTH
dest_scroll_message = ""
dest_scroll_pos = OLED_WIDTH
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
        "BCNOFNe KERNEL "
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
    global fan_ctrl, oled_display, pi
    if not HARDWARE_AVAILABLE:
        return

    # pigpio Setup
    try:
        # Docker環境からホストの pigpiod に接続するための設定
        # 1. 環境変数を優先 2. 特殊なホスト名 3. デフォルト
        pigpio_host = os.getenv("PIGPIO_ADDR", "localhost")
        
        pi = pigpio.pi(pigpio_host)
        
        # もし localhost で接続失敗し、かつ環境変数が未設定なら、Docker Gateway を試行
        if not pi.connected and pigpio_host == "localhost":
            logger.info("OLED/FAN: Retrying pigpiod on 172.17.0.1 (Docker bridge)...")
            pi = pigpio.pi("172.17.0.1")

        if not pi.connected:
            print("[OLED/FAN] WARN: pigpiod not running or unreachable. Fan control will be stubbed.")
        else:
            fan_ctrl = FanController(pi, pwm_pin=FAN_PWM_PIN, tach_pin=FAN_TACH_PIN)
            print(f"[OLED/FAN] INFO: FanController initialized with pigpio on {pi._host}.")
    except Exception as e:
        logger.error(f"OLED/FAN: Failed to initialize pigpio/fan: {e}")

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
    global fan_ctrl, fan_status
    if not HARDWARE_AVAILABLE:
        return

    if fan_ctrl:
        try:
            fan_ctrl.update(temp)
            fan_status = fan_ctrl.get_status()
        except Exception as e:
            logger.error(f"OLED/FAN: Fan control error: {e}")

def get_system_state_val(db: Session, key: str, default: str) -> str:
    # 別プロセス（core等）が書き込んだ最新の値を読むため、キャッシュを破棄してからクエリ
    db.expire_all()
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
    global scroll_pos, scroll_message, dest_scroll_pos, dest_scroll_message
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
    
    # Network info from DB (updated by core on startup)
    ip = get_system_state_val(db, "HOST_IP", "??") 
    ts_ip = get_system_state_val(db, "TAILSCALE_IP", "??")
    
    # Webhook は表示しない（長すぎてLAN/TS IPが見えなくなるため）
    ip_scroll = f"LAN:{ip} TS:{ts_ip}"
    
    # Scroll message setup
    new_scroll = clean_text(get_system_state_val(db, "oled_scroll_msg", "System Online"))
    total_scroll = f"{new_scroll} | {ip_scroll}"
    
    if total_scroll != scroll_message:
        scroll_message = total_scroll
        scroll_pos = OLED_WIDTH

    # DEST scroll message setup (AI goal - full text scroll)
    goal_raw = get_system_state_val(db, "ai_target_goal", "---")
    new_dest = clean_text(goal_raw)
    if new_dest != dest_scroll_message:
        dest_scroll_message = new_dest
        dest_scroll_pos = OLED_WIDTH
    
    # Internal State を取得して顔文字に反映
    latest_state = db.query(InternalStateHistory).order_by(InternalStateHistory.id.desc()).first()
    if latest_state:
        ai_face = INTERNAL_STATE_FACE.get(latest_state.state_name, "(o_o)")
    else:
        ai_face = "(^-^)"
        
    # ハードウェアエラー等による上書き（優先）
    if score < 40 and temp >= 60:
        ai_face = "(x_x)" 
    elif ai_status == "STOPPED":
        ai_face = "(-_-)"


    image = Image.new("1", (OLED_WIDTH, OLED_HEIGHT))
    draw = ImageDraw.Draw(image)
    
    try:
        # 日本語表示用フォントをロード (複数パスを試行)
        jp_font_paths = [
            "/usr/share/fonts/opentype/noto/NotoSansCJK-Regular.ttc",
            "/usr/share/fonts/truetype/noto/NotoSansCJK-Regular.ttc",
            "/usr/share/fonts/opentype/noto/NotoSansCJKjp-Regular.otf",
            "/usr/share/fonts/truetype/noto/NotoSansMono-Regular.ttf",
            "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf",
        ]
        font = None
        for p in jp_font_paths:
            if os.path.exists(p):
                font = ImageFont.truetype(p, 10)
                break
        if not font:
            font = ImageFont.load_default()
            print("[OLED] WARN: No TrueType font found, using default. Japanese may not render.")
        else:
            print(f"[OLED] INFO: Font loaded from {p}")
    except Exception as e:
        logger.error(f"Failed to load font: {e}")
        font = ImageFont.load_default()
        
    # ====== DRAWING ======
    # Line 1: BCNOFNe: SAIL >===> [~]
    draw.text((0, 0), clean_text(f"BCNOFNe:{mode_disp} {mode_emoji}"), font=font, fill=255)
    
    # Line 2: DEST: [Goal] (全文スクロール)
    draw.text((dest_scroll_pos, 11), f"DEST:{dest_scroll_message}", font=font, fill=255)
    
    # Line 3: AI: (face)
    draw.text((0, 22), f"AI: {ai_face}", font=font, fill=255)
    
    # Line 4: Hardwares (TEMP/DISK)
    draw.text((0, 33), f"TEMP:{temp:.0f}C DISK:{disk_pct:.0f}%", font=font, fill=255)
    
    # Line 5: Fan status (Duty/RPM)
    draw.text((0, 44), f"FAN:{fan_status['duty']}% RPM:{fan_status['rpm']}", font=font, fill=255)
    
    # Line 6: Scrolling message (LAN/TS IPs)
    draw.text((scroll_pos, 55), scroll_message, font=font, fill=255)

    
    # スクロール位置更新 (IP行)
    scroll_pos -= 5
    max_len = len(scroll_message) * 7
    if scroll_pos < -max_len:
        scroll_pos = OLED_WIDTH

    # スクロール位置更新 (DEST行)
    dest_scroll_pos -= 5
    dest_max_len = len(dest_scroll_message) * 8  # 日本語文字は幅広
    if dest_scroll_pos < -dest_max_len:
        dest_scroll_pos = OLED_WIDTH
        
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
            db.expire_all()
            await asyncio.sleep(0.1)
    except Exception as e:
        logger.error(f"Hardware loop error: {e}")
    finally:
        db.close()
        if HARDWARE_AVAILABLE:
            if fan_ctrl:
                fan_ctrl.stop()
            if pi:
                pi.stop()

@asynccontextmanager
async def lifespan(app: FastAPI):
    # Startup
    task = asyncio.create_task(hardware_loop())
    yield
    # Shutdown
    task.cancel()
    if HARDWARE_AVAILABLE:
        show_shutdown_animation()
        if fan_ctrl:
            fan_ctrl.stop()
        if pi:
            pi.stop()

app.router.lifespan_context = lifespan

@app.get("/health")
def health_check():
    return {
        "status": "ok",
        "service": "oled-controller",
        "hardware_present": HARDWARE_AVAILABLE,
        "fan_duty": fan_status.get("duty", 0),
        "fan_rpm": fan_status.get("rpm", 0),
        "cpu_temp": get_cpu_temp()
    }
