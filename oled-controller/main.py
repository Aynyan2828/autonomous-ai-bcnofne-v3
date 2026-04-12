import os
import sys
import time
import asyncio
import psutil
import socket
from fastapi import FastAPI
from sqlalchemy.orm import Session
from contextlib import asynccontextmanager

sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from shared import init_db
from shared.database import SessionLocal
from shared.models import SystemState, InternalStateHistory
from shared.logger import ShipLogger

# データベース初期化
init_db()

logger = ShipLogger("oled-controller")

# OLED & Fan dependencies
try:
    import pigpio
    from .fan_controller import FanController
    from .oled_screensaver import BCNOFNeScreenSaver
    import board
    import busio
    import adafruit_ssd1306
    from PIL import Image, ImageDraw, ImageFont
    HARDWARE_AVAILABLE = True
except ImportError:
    try:
        import pigpio
        from fan_controller import FanController
        from oled_screensaver import BCNOFNeScreenSaver
        import board
        import busio
        import adafruit_ssd1306
        from PIL import Image, ImageDraw, ImageFont
        HARDWARE_AVAILABLE = True
    except Exception as e:
        HARDWARE_AVAILABLE = False
        print(f"[OLED/FAN] Hardware libraries not available. Running in stub mode. ({e})")

def clean_text(text: str) -> str:
    if not text: return ""
    return "".join(c for c in text if ord(c) >= 32 or c == '\n')

app = FastAPI(title="BCNOFNe OLED & Fan Controller")

# Configuration
OLED_WIDTH = 128
OLED_HEIGHT = 64
FAN_PWM_PIN = 13
FAN_TACH_PIN = 24
TEMP_THRESHOLD_HIGH = 60.0
TEMP_THRESHOLD_LOW = 40.0

SHIP_MODE_DISPLAY = {
    "autonomous": "SAIL  >===>", "user_first": "PORT  >===>",
    "maintenance": "DOCK  >===>", "power_save": "ANCHOR>===>",
    "safe": "SOS   >===>", "SAIL": "SAIL  >===>",
    "PORT": "PORT  >===>", "DOCK": "DOCK  >===>",
    "ANCHOR": "ANCHOR>===>", "SOS": "SOS   >===>",
}

SHIP_MODE_EMOJI = {
    "autonomous": "[~]", "user_first": "[P]", "maintenance": "[M]",
    "power_save": "[z]", "safe": "[!]", "SAIL": "[~]",
    "PORT": "[P]", "DOCK": "[M]", "ANCHOR": "[z]", "SOS": "[!]",
}

AI_STATE_FACE = {
    "Idle": "(-_-)", "Planning": "( ..)phi", "Acting": "(o_o)",
    "Moving Files": "( ..)phi", "Error": "(x_x)", "Wait": "(o_o)",
    "RUNNING": "(o_o)", "STOPPED": "(x_x)",
}

INTERNAL_STATE_FACE = {
    "CALM": "(^-^)", "STORM": "(>_<)", "TIRED": "(=_=)",
    "FOCUSED": "(*_*)", "CURIOUS": "(O_O)", "RELIEVED": "(^o^)",
    "PROUD": "(`_`)"
}

# Runtime Variables
fan_ctrl = None
pi = None
fan_status = {"duty": 0, "rpm": 0, "status": "INITIALIZING"}
oled_display = None
scroll_message = ""
scroll_pos = OLED_WIDTH
dest_scroll_message = ""
dest_scroll_pos = OLED_WIDTH
last_display_data = {}
last_activity_ts = time.time()
oled_mode = "NORMAL"
screensaver = None

SCREENSAVER_IDLE_SECONDS = int(os.getenv("SCREENSAVER_IDLE_SECONDS", "60"))
ENABLE_SCREENSAVER = os.getenv("ENABLE_SCREENSAVER", "true").lower() == "true"
LOGO_PATH = "/app/oled_128x64_resize_dither.png"

def show_boot_animation():
    """Ship-like boot sequence animation with logo and progress bar."""
    if not HARDWARE_AVAILABLE or not oled_display:
        return
    
    logo = None
    paths_to_try = [LOGO_PATH, "oled_128x64_resize_dither.png", "./oled-controller/oled_128x64_resize_dither.png"]
    for p in paths_to_try:
        if os.path.exists(p):
            try:
                logo = Image.open(p).convert("1")
                break
            except: pass

    checks = ["CPU TEMPERATURE", "I2C BUS STATUS", "FAN CONTROLLER", "DATABASE CONN", "NETWORK CONFIG", "BCNOFNe KERNEL "]
    total_checks = len(checks)
    
    for i, label in enumerate(checks):
        if not oled_display: break
        image = logo.copy() if logo else Image.new("1", (OLED_WIDTH, OLED_HEIGHT))
        draw = ImageDraw.Draw(image)
        
        # テキスト背景の黒塗り（元のロジック通り）
        draw.rectangle((0, 0, 110, 10), fill=0)
        draw.text((0, 0), "--- SYSTEM CHECK ---", font=ImageFont.load_default(), fill=255)
        
        y_pos = 12
        draw.rectangle((0, y_pos, 120, y_pos + 9), fill=0)
        draw.text((0, y_pos), f"[ OK ] {label}", font=ImageFont.load_default(), fill=255)
            
        # プログレスバー（元のロジック通り fill=0 を追加）
        bar_y, bar_h = 54, 8
        draw.rectangle((0, bar_y, OLED_WIDTH - 1, bar_y + bar_h), outline=255, fill=0)
        progress_w = int((i + 1) / total_checks * (OLED_WIDTH - 4))
        draw.rectangle((2, bar_y + 2, 2 + progress_w, bar_y + bar_h - 2), fill=255)
        
        oled_display.image(image)
        oled_display.show()
        time.sleep(0.5)
    
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
    if not HARDWARE_AVAILABLE or not oled_display: return
    logo = None
    if os.path.exists(LOGO_PATH):
        try: logo = Image.open(LOGO_PATH).convert("1")
        except: pass

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

    if logo:
        image = logo.copy()
        for y in range(0, OLED_HEIGHT // 2, 2):
            draw = ImageDraw.Draw(image)
            draw.line((0, y, OLED_WIDTH, y), fill=0)
            draw.line((0, OLED_HEIGHT - 1 - y, OLED_WIDTH, OLED_HEIGHT - 1 - y), fill=0)
            oled_display.image(image)
            oled_display.show()
            time.sleep(0.05)

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
    global fan_ctrl, oled_display, pi, screensaver
    if not HARDWARE_AVAILABLE: return
    try:
        pi = pigpio.pi(os.getenv("PIGPIO_ADDR", "localhost"))
        if not pi.connected:
            pi = pigpio.pi("host.docker.internal")
        if pi.connected:
            fan_ctrl = FanController(pi, pwm_pin=FAN_PWM_PIN, tach_pin=FAN_TACH_PIN)
    except: pass

    try:
        i2c = busio.I2C(board.SCL, board.SDA)
        oled_display = adafruit_ssd1306.SSD1306_I2C(OLED_WIDTH, OLED_HEIGHT, i2c)
        screensaver = BCNOFNeScreenSaver(OLED_WIDTH, OLED_HEIGHT)
        show_boot_animation()
    except: oled_display = None

def get_cpu_temp():
    try:
        with open("/sys/class/thermal/thermal_zone0/temp", "r") as f:
            return int(f.read()) / 1000.0
    except: return 0.0

def control_fan(temp, load=0.0):
    global fan_ctrl, fan_status
    if fan_ctrl:
        try:
            fan_ctrl.update(temp, load)
            fan_status = fan_ctrl.get_status()
            if fan_status["status"] != getattr(control_fan, "last_label", ""):
                control_fan.last_label = fan_status["status"]
                logger.debug(f"OLED/FAN: Status -> {fan_status['status']} ({temp:.1f}C)")
        except: pass

def discover_ips():
    h, t = "???", "???"
    try:
        for _, addrs in psutil.net_if_addrs().items():
            for a in addrs:
                if a.family == socket.AF_INET:
                    ip = a.address
                    if ip.startswith("100."): t = ip
                    elif (ip.startswith("192.168.") or ip.startswith("10.")) and not ip.startswith("172."):
                        if h == "???": h = ip
    except: pass
    return h, t

def get_system_state_val(db: Session, key: str, default: str) -> str:
    if not db: return default
    try:
        db.expire_all()
        state = db.query(SystemState).filter_by(key=key).first()
        return state.value if state else default
    except: return default

def compute_mood(temp: float, ai_status: str, ship_mode: str) -> tuple[int, str]:
    score = 80
    if temp >= 75: score -= 35
    elif temp >= 65: score -= 20
    elif 0 < temp <= 45: score += 5
    st = (ai_status or "").lower()
    if "error" in st or "stop" in st or ship_mode == "safe": score -= 25
    elif "wait" in st: score -= 8
    elif "run" in st: score += 2
    score = max(0, min(100, score))
    if score >= 85: f = "(^o^)"
    elif score >= 70: f = "(^_^)"
    elif score >= 55: f = "(o_o)"
    elif score >= 35: f = "(._.)"
    else: f = "(x_x)" if temp >= 70 else "(>_<)"
    return score, f

def update_oled(db: Session):
    global scroll_pos, scroll_message, dest_scroll_pos, dest_scroll_message
    global last_display_data, last_activity_ts, oled_mode, screensaver
    if not HARDWARE_AVAILABLE or not oled_display: return
    now = time.time()
    if not hasattr(update_oled, "cache"):
        update_oled.cache = {"ai_status":"RUNNING", "ship_mode":"autonomous", "ai_face":"(o_o)", "goal":"---", "scroll":"System Online", "ip":"???", "ts_ip":"???"}

    if db:
        try:
            update_oled.cache["ai_status"] = get_system_state_val(db, "ai_status", "RUNNING")
            update_oled.cache["ship_mode"] = get_system_state_val(db, "ship_mode", "autonomous")
            latest = db.query(InternalStateHistory).order_by(InternalStateHistory.id.desc()).first()
            update_oled.cache["ai_face"] = INTERNAL_STATE_FACE.get(latest.state_name, "(o_o)") if latest else "(^-^)"
            update_oled.cache["goal"] = get_system_state_val(db, "ai_target_goal", "---")
            update_oled.cache["scroll"] = get_system_state_val(db, "oled_scroll_msg", "System Online")
            h, t = discover_ips()
            update_oled.cache["ip"], update_oled.cache["ts_ip"] = h, t
        except: pass

    if oled_mode == "SCREENSAVER" and ENABLE_SCREENSAVER and screensaver:
        image = Image.new("1", (OLED_WIDTH, OLED_HEIGHT))
        try:
            screensaver.update()
            screensaver.draw(ImageDraw.Draw(image))
            oled_display.image(image)
            oled_display.show()
        except: pass
        return

    c = update_oled.cache
    temp = get_cpu_temp()
    score, _ = compute_mood(temp, c["ai_status"], c["ship_mode"])
    m_disp = SHIP_MODE_DISPLAY.get(c["ship_mode"], "SAIL")
    m_emoji = SHIP_MODE_EMOJI.get(c["ship_mode"], "[~]")
    try: disk = psutil.disk_usage('/').percent
    except: disk = 0.0
    
    total_scroll = f"{clean_text(c['scroll'])} | LAN:{c['ip']} TS:{c['ts_ip']}"
    if total_scroll != scroll_message: scroll_message, scroll_pos = total_scroll, OLED_WIDTH
    new_dest = clean_text(c["goal"])
    if new_dest != dest_scroll_message: dest_scroll_message, dest_scroll_pos = new_dest, OLED_WIDTH

    cur = {"stat":c["ai_status"], "mode":c["ship_mode"], "dest":new_dest, "msg":c["scroll"]}
    if cur != last_display_data:
        last_display_data, last_activity_ts = cur, now
        if oled_mode != "NORMAL": oled_mode = "NORMAL"

    image = Image.new("1", (OLED_WIDTH, OLED_HEIGHT))
    draw = ImageDraw.Draw(image)
    if not hasattr(update_oled, "font"):
        update_oled.font = ImageFont.load_default()
        for p in ["/usr/share/fonts/opentype/noto/NotoSansCJK-Regular.ttc", "/usr/share/fonts/truetype/noto/NotoSansCJK-Regular.ttc"]:
            if os.path.exists(p):
                update_oled.font = ImageFont.truetype(p, 10); break
    f = update_oled.font
    ai_f = c["ai_face"]
    if score < 40 and temp >= 60: ai_f = "(x_x)"
    elif c["ai_status"] == "STOPPED": ai_f = "(-_-)"

    draw.text((0, 0), f"BCN:{m_disp} {m_emoji}", font=f, fill=255)
    draw.text((dest_scroll_pos, 11), f"DEST:{dest_scroll_message}", font=f, fill=255)
    draw.text((0, 22), f"AI: {ai_f}", font=f, fill=255)
    draw.text((0, 33), f"TEMP:{temp:.0f}C DISK:{disk:.0f}%", font=f, fill=255)
    draw.text((0, 44), f"FAN:{fan_status['duty']}% RPM:{fan_status['rpm']}", font=f, fill=255)
    draw.text((scroll_pos, 55), scroll_message, font=f, fill=255)

    scroll_pos -= 5
    if scroll_pos < -(len(scroll_message)*7): scroll_pos = OLED_WIDTH
    dest_scroll_pos -= 5
    if dest_scroll_pos < -(len(dest_scroll_message)*8): dest_scroll_pos = OLED_WIDTH
    oled_display.image(image)
    oled_display.show()

async def hardware_loop():
    global oled_mode, last_activity_ts
    setup_hardware()
    last_db = 0
    while True:
        try:
            now = time.time()
            if now - last_db >= 2.0:
                control_fan(get_cpu_temp(), psutil.cpu_percent())
                db = SessionLocal()
                try: update_oled(db)
                finally: db.close()
                last_db = now
            else: update_oled(None)

            if ENABLE_SCREENSAVER and oled_mode == "NORMAL" and (now - last_activity_ts) > SCREENSAVER_IDLE_SECONDS:
                logger.info("OLED: Entering SCREENSAVER mode")
                oled_mode = "SCREENSAVER"
            await asyncio.sleep(0.5)
        except Exception as e:
            logger.error(f"Loop error: {e}")
            await asyncio.sleep(1.0)

@asynccontextmanager
async def lifespan(app: FastAPI):
    task = asyncio.create_task(hardware_loop())
    yield
    task.cancel()
    if HARDWARE_AVAILABLE:
        show_shutdown_animation()
        if pi: pi.stop()

app.router.lifespan_context = lifespan

@app.get("/health")
def health_check():
    return {"status":"ok", "fan":fan_status, "temp":get_cpu_temp()}
