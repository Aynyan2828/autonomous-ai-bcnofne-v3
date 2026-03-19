import pigpio
import time
from shared.logger import ShipLogger
logger = ShipLogger("oled-fan")

# ------------------------------------------------------------------------
# 設定
# (将来的に JSON/YAML で外出し可能なように分離しています)
# ------------------------------------------------------------------------
CONFIG = {
    "metric_mode": "load", # 'temperature' or 'load' (RGB based on load, Fan based on temp)
    "update_interval": 0.1,       # 制御・計算の更新周期 (0.1s に短縮してレスポンス向上)
    "fan_min_duty": 30,
    "fan_max_duty": 100,
    "fan_temp_min": 40,
    "fan_temp_max": 60,
    "duty_step": 5,               # 1回の更新で変化できるDuty最大幅
    "rgb_enabled": True,          # ハード未接続時は初期化で自動Falseにフォールバックさせます
    "rgb_smoothing_step": 100,    # RGB値(0-255)の最大変化量/回 (値を大きくすると変化が早くなります)
    "states": [
        {"max_temp": 40, "max_load": 10, "label": "DOCKED",        "rgb": [0, 0, 255]},       # 青
        {"max_temp": 50, "max_load": 30, "label": "CRUISING",      "rgb": [0, 255, 255]},     # 水色
        {"max_temp": 60, "max_load": 60, "label": "ENGINE RISING", "rgb": [0, 255, 0]},       # 緑
        {"max_temp": 70, "max_load": 80, "label": "HOT",           "rgb": [255, 255, 0]},     # 黄
        {"max_temp": 75, "max_load": 95, "label": "OVERHEAT",      "rgb": [255, 128, 0]},     # 橙
        {"max_temp": 999,"max_load": 999,"label": "HEAT ALERT",    "rgb": [255, 0, 0]}        # 赤
    ]
}

class SystemThermalController:
    """
    BCNOFNe v3: 統合型 4-pin PWM Fan & RGB Controller
    システム熱状態(Thermal State)から、ファンとRGBを安全かつ連動して制御します。
    """
    def __init__(self, pi, pwm_pin=13, tach_pin=24): # ユーザー配線: Fan PWM=13, TACH=24 / RGB=18
        self.pi = pi
        self.cb = None
        self.strip = None
        self.pwm_pin = pwm_pin
        self.tach_pin = tach_pin
        self.config = CONFIG
        
        # ファン状態
        self.target_duty = self.config["fan_min_duty"]
        self.current_duty = self.config["fan_min_duty"]
        self.rpm = 0
        self._pulses = 0
        self._last_rpm_time = time.time()
        
        # RGB・表示状態
        self.current_rgb = [0, 0, 255]
        self.target_rgb = [0, 0, 255]
        self.current_status_label = "INIT"
        self.current_temp = 0.0
        self.current_load = 0.0
        
        self._init_hardware()

    def _init_hardware(self):
        """ ファン制御・RPM測定に加え、RGBハードウェアの初期化を行う """
        if self.pi.connected:
            self.pi.set_mode(self.pwm_pin, pigpio.OUTPUT)
            self.pi.set_PWM_frequency(self.pwm_pin, 25000) # 25kHz標準
            self.pi.set_PWM_range(self.pwm_pin, 100)
            self.pi.set_PWM_dutycycle(self.pwm_pin, self.current_duty)
            
            self.pi.set_mode(self.tach_pin, pigpio.INPUT)
            self.pi.set_pull_up_down(self.tach_pin, pigpio.PUD_UP)
            self.cb = self.pi.callback(self.tach_pin, pigpio.FALLING_EDGE, self._tach_callback)
            
            self._init_rgb_hardware()
            logger.info(f"SystemThermalController: Init OK (PWM={self.pwm_pin}, TACH={self.tach_pin})")
        else:
            logger.warning("SystemThermalController: pigpio not connected. Running in stub mode.")

    def _init_rgb_hardware(self):
        """
        RGB初期化 (ZP-0129付属RGBハブ: GPIO18接続, WS281B)
        """
        if not self.config['rgb_enabled']:
            return
            
        if self.pwm_pin in [12, 18]:
            logger.error(f"SystemThermalController: PWM pin {self.pwm_pin} CONFLICTS with WS281x RGB (on PWM Channel 0) on ZP-0129. RGB Disabled.")
            self.config['rgb_enabled'] = False
            return
            
        try:
            from rpi_ws281x import PixelStrip, ws
            # ZP-0129の標準設定 (ファン+基板上のムードライト)
            LED_COUNT      = 4       # 実際のLED数に合わせて後から増減可能
            LED_PIN        = 18      # GPIO18 (PWM0)
            LED_FREQ_HZ    = 800000 
            LED_DMA        = 10      
            LED_BRIGHTNESS = 255     
            LED_INVERT     = False   
            LED_CHANNEL    = 0       
            # WS2812Bは一般的にGRB順序のため明示指定
            LED_STRIP      = ws.WS2811_STRIP_RGB 
            
            self.strip = PixelStrip(LED_COUNT, LED_PIN, LED_FREQ_HZ, LED_DMA, LED_INVERT, LED_BRIGHTNESS, LED_CHANNEL, LED_STRIP)
            self.strip.begin()
            
            logger.info("SystemThermalController: WS281x RGB hardware initialized (RGB Mode) on GPIO 18.")
            # 起動時の同期: 最初の一回を強制反映
            self._apply_rgb_hardware(self.current_rgb)
        except ImportError:
            logger.warning("SystemThermalController: 'rpi_ws281x' module missing. RGB Disabled.")
            self.config['rgb_enabled'] = False
        except RuntimeError as e:
            logger.warning(f"SystemThermalController: WS281x Init failed. RGB Disabled. Error: {e}")
            self.config['rgb_enabled'] = False
        except Exception as e:
            logger.error(f"SystemThermalController: Unknown RGB Error: {e}")
            self.config['rgb_enabled'] = False

    def _apply_rgb_hardware(self, rgb_list):
        """ 実際のLEDへ色データを送信 (WS281x) """
        if not getattr(self, 'strip', None) or not self.config['rgb_enabled']:
            return
            
        try:
            from rpi_ws281x import Color
            # デバッグログ追加
            logger.info(f"SystemThermalController: Setting RGB -> {rgb_list}")
            
            # ZP-0129のWS281Bへ色送信
            color_val = Color(int(rgb_list[0]), int(rgb_list[1]), int(rgb_list[2]))
            for i in range(self.strip.numPixels()):
                self.strip.setPixelColor(i, color_val)
            self.strip.show()
        except Exception as e:
            logger.error(f"SystemThermalController: RGB Write Error: {e}")
            pass

    def _tach_callback(self, gpio, level, tick):
        self._pulses += 1

    def _calc_gradient_rgb(self, load):
        """ CPU負荷(0-100)に応じたグラデーション色を計算する (Blue -> Cyan -> Green -> Yellow -> Red) """
        # カラーポイント定義: (位置, R, G, B)
        points = [
            (0,   0,   0,   255), # 0%:   Blue
            (25,  0,   255, 255), # 25%:  Cyan
            (50,  0,   255, 0),   # 50%:  Green
            (75,  255, 255, 0),   # 75%:  Yellow
            (100, 255, 0,   0)    # 100%: Red
        ]
        
        load = max(0, min(100, load))
        
        for i in range(len(points) - 1):
            p1 = points[i]
            p2 = points[i+1]
            if load <= p2[0]:
                # 線形補間
                ratio = (load - p1[0]) / (p2[0] - p1[0])
                r = int(p1[1] + (p2[1] - p1[1]) * ratio)
                g = int(p1[2] + (p2[2] - p1[2]) * ratio)
                b = int(p1[3] + (p2[3] - p1[3]) * ratio)
                return [r, g, b]
        return [255, 0, 0] # Fallback

    def _derive_status(self, temp, load):
        """ 現在の温度・負荷から Thermal State を導出する """
        # ファン制御は温度ベースで固定
        check_val = temp
        check_key = "max_temp"
        
        for state in self.config["states"]:
            if check_val <= state[check_key]:
                return state
        return self.config["states"][-1] # Fallback (最大危険状態)

    def _map_temp_to_fan_target(self, temp):
        """ 温度から目標のPWM Dutyを計算（線形補間） """
        c_min = self.config["fan_temp_min"]
        c_max = self.config["fan_temp_max"]
        d_min = self.config["fan_min_duty"]
        d_max = self.config["fan_max_duty"]
        
        if temp <= c_min: return d_min
        if temp >= c_max: return d_max
        return d_min + (temp - c_min) * (d_max - d_min) / (c_max - c_min)

    def _calc_rpm(self, elapsed):
        """ 蓄積パルスからRPMを算出 """
        if elapsed > 0:
            self.rpm = int((self._pulses / 2) * (60 / elapsed))
        self._pulses = 0
        self._last_rpm_time = time.time()

    def _smooth_duty_change(self):
        """ ファンの回転をステップ幅（5%）で除々に変化させる """
        diff = self.target_duty - self.current_duty
        step = self.config["duty_step"]
        if abs(diff) <= step:
            self.current_duty = self.target_duty
        else:
            self.current_duty += step if diff > 0 else -step

        if self.pi.connected:
            self.pi.set_PWM_dutycycle(self.pwm_pin, int(self.current_duty))

    def _smooth_rgb_transition(self):
        """ RGBの色をステップ幅(10/255)で除々に変化させる """
        step = self.config["rgb_smoothing_step"]
        changed = False
        for i in range(3):
            diff = self.target_rgb[i] - self.current_rgb[i]
            if abs(diff) <= step:
                if self.current_rgb[i] != self.target_rgb[i]:
                    self.current_rgb[i] = self.target_rgb[i]
                    changed = True
            else:
                self.current_rgb[i] += step if diff > 0 else -step
                changed = True
        
        if changed and self.config["rgb_enabled"]:
            self._apply_rgb_hardware(self.current_rgb)

    def update(self, temp, load=0.0):
        """
        外部から定期的に呼び出される主状態更新ループ
        (load は現時点で未提供でも動作するデフォルト 0.0 仕様)
        """
        if not self.pi.connected: return
        
        self.current_temp = temp
        self.current_load = load

        # 1. 状態の決定
        state = self._derive_status(temp, load)
        if state["label"] != self.current_status_label:
            logger.info(f"SystemThermalController: State Change -> {state['label']} (Temp={temp:.1f}C, Load={load:.1f}%)")
        self.current_status_label = state["label"]
        
        # RGBの決定 (metric_mode が load ならグラデーション)
        if self.config["metric_mode"] == "load":
            self.target_rgb = self._calc_gradient_rgb(load)
        else:
            self.target_rgb = state["rgb"]

        # 2. ファンDutyの決定
        self.target_duty = self._map_temp_to_fan_target(temp)

        # 3. ハードウェアへの反映 (スムージング)
        self._smooth_duty_change()
        self._smooth_rgb_transition()

        # 4. RPM計算 (指定した計算インターバルを超えたら実行)
        elapsed = time.time() - self._last_rpm_time
        if elapsed >= self.config["update_interval"]:
            self._calc_rpm(elapsed)

    def get_status(self):
        """
        外部連携(OLED表示器・Web UI等)向けの状態リターン
        Dict型で返すため、JSON serialize も容易
        """
        return {
            "temp": round(self.current_temp, 1),
            "cpu_load": round(self.current_load, 1),
            "duty": int(self.current_duty),
            "target": int(self.target_duty),
            "rpm": self.rpm,
            "rgb": [int(c) for c in self.current_rgb],
            "status": self.current_status_label
        }

    def stop(self):
        """ 終了時のフェイルセーフ処理 """
        if self.pi.connected:
            self.pi.set_PWM_dutycycle(self.pwm_pin, 100) # ファン全開
            if self.cb: 
                self.cb.cancel()
            
            # RGBフェイルセーフ (異常を示す赤色に固定、またはトラブル時は消灯)
            if self.config["rgb_enabled"]:
                self.target_rgb = [255, 0, 0]
                self.current_rgb = [255, 0, 0]
                self._apply_rgb_hardware(self.current_rgb)
                
            logger.info("SystemThermalController: Stopped (Fan=100%, RGB=RED)")

# ------------------------------------------------------------------------
# 古い呼び出し元との上位互換ラッパー
# ------------------------------------------------------------------------
class FanController(SystemThermalController):
    """
    既存の `FanController` インスタンス化の互換性を保つためのラッパー。
    そのまま置き換え可能です。
    """
    def __init__(self, pi, pwm_pin=13, tach_pin=24): # ユーザー配線: PWM=13, TACH=24
        super().__init__(pi, pwm_pin, tach_pin)

    # 上位の update() が tempとload(デフォルト0.0) を受け取るため
    # 引数が temp だけの場合も安全に吸収します。
    def update(self, temp, load=0.0):
        super().update(temp, load)
