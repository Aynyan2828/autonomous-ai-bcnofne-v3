import pigpio
import time
import sys
import logging

# ログをコンソールに出力する設定
logging.basicConfig(level=logging.DEBUG, format='%(asctime)s - %(levelname)s - %(message)s')

def test_fan():
    logging.info("Initializing pigpio...")
    pi = pigpio.pi()
    if not pi.connected:
        logging.error("pigpio daemon is not running! Please run 'sudo systemctl start pigpiod'")
        sys.exit(1)

    logging.info("Importing SystemThermalController...")
    from fan_controller import SystemThermalController

    try:
        logging.info("Creating SystemThermalController instance (PWM=12, TACH=24)...")
        controller = SystemThermalController(pi, pwm_pin=12, tach_pin=24)
        
        logging.info("Controller created. Entering test loop (Simulating temp=55°C, Blue->Green).")
        logging.info("Press Ctrl+C to exit and stop the test.")
        
        for i in range(10):
            # 55度は「水色（CRUISING）〜緑（ENGINE RISING）」付近
            controller.update(temp=55.0, load=0.0)
            status = controller.get_status()
            logging.info(f"Target Duty: {status['target']}%, Current Duty: {status['duty']}%, RPM: {status['rpm']}, RGB: {status['rgb']}, Status: {status['status']}")
            time.sleep(1.0)
            
    except KeyboardInterrupt:
        logging.info("Test stopped by user.")
    except Exception as e:
        logging.exception(f"An error occurred during runtime: {e}")
    finally:
        if 'controller' in locals():
            logging.info("Stopping controller (Fail-safe)...")
            controller.stop()
        pi.stop()

if __name__ == "__main__":
    test_fan()
