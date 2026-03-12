import pigpio
import time
import logging

class FanController:
    """
    4-pin PWM Fan Controller using pigpio for BCNOFNe v3.
    Features:
    - 25kHz PWM on GPIO18 for quiet operation.
    - RPM measurement via GPIO23 (2 pulses per revolution).
    - Smooth duty cycle transitions.
    - Temperature-based linear control (40°C: 30% -> 60°C: 100%).
    """
    def __init__(self, pi, pwm_pin=18, tach_pin=23):
        self.pi = pi
        self.pwm_pin = pwm_pin
        self.tach_pin = tach_pin
        
        self.target_duty = 30
        self.current_duty = 30
        self.rpm = 0
        self._pulses = 0
        self._last_rpm_time = time.time()
        
        # Initialize PWM
        if self.pi.connected:
            self.pi.set_mode(self.pwm_pin, pigpio.OUTPUT)
            self.pi.set_PWM_frequency(self.pwm_pin, 25000) # 25kHz standard for 4-pin fans
            self.pi.set_PWM_range(self.pwm_pin, 100)
            self.pi.set_PWM_dutycycle(self.pwm_pin, self.current_duty)
            
            # Initialize Tachometer
            self.pi.set_mode(self.tach_pin, pigpio.INPUT)
            self.pi.set_pull_up_down(self.tach_pin, pigpio.PUD_UP)
            self.cb = self.pi.callback(self.tach_pin, pigpio.FALLING_EDGE, self._tach_callback)
            
            print(f"[FAN] FanController: Initialized on BCM PWM={pwm_pin}, TACH={tach_pin}")
        else:
            print("[FAN] FanController: pigpio not connected. Running in stub mode.")

    def _tach_callback(self, gpio, level, tick):
        self._pulses += 1
        
    def update(self, temp):
        """
        Update fan speed based on CPU temperature.
        Expected to be called periodically (e.g., every 1-5 seconds).
        """
        if not self.pi.connected:
            return

        # Linear mapping logic
        # Below 40C: 30%
        # Above 60C: 100%
        if temp <= 40:
            target = 30
        elif temp >= 60:
            target = 100
        else:
            # 30 + (temp - 40) * (100 - 30) / (60 - 40)
            target = 30 + (temp - 40) * 3.5
            
        self.target_duty = int(target)
        
        # Smoothing: move 5% per update step at most for gradual changes
        diff = self.target_duty - self.current_duty
        step = 5
        if abs(diff) <= step:
            self.current_duty = self.target_duty
        else:
            self.current_duty += step if diff > 0 else -step
            
        self.pi.set_PWM_dutycycle(self.pwm_pin, self.current_duty)
        
        # Calculate RPM every ~1 second
        now = time.time()
        elapsed = now - self._last_rpm_time
        if elapsed >= 1.0:
            # RPM = (pulses / 2) * (60 / elapsed)
            # 2 pulses per revolution is standard for PC fans.
            self.rpm = int((self._pulses / 2) * (60 / elapsed))
            
            # デバッグ出力: ログで見えるように print を使用
            if self._pulses > 0:
                print(f"[FAN] Measured {self._pulses} pulses in {elapsed:.2f}s -> {self.rpm} RPM")
            elif self.target_duty > 30:
                # Duty が出てるのにパルスが0なら異常
                level = self.pi.read(self.tach_pin)
                print(f"[FAN] No pulses detected. Current pin level on BCM {self.tach_pin} is {level}")

            self._pulses = 0
            self._last_rpm_time = now

    def get_status(self):
        return {
            "duty": self.current_duty,
            "rpm": self.rpm,
            "target": self.target_duty
        }
        
    def stop(self):
        """Clean up or set to fail-safe state."""
        if self.pi.connected:
            self.pi.set_PWM_dutycycle(self.pwm_pin, 100) # Fail-safe: full speed on exit
            if hasattr(self, 'cb'):
                self.cb.cancel()
            logging.info("FanController: Stopped (Set to 100% fail-safe)")
