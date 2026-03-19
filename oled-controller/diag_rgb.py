import time
import sys
import os

# ZP-0129 default settings
LED_COUNT = 4
LED_PIN = 18
LED_FREQ_HZ = 800000
LED_DMA = 10
LED_BRIGHTNESS = 255
LED_INVERT = False
LED_CHANNEL = 0

def test_colors():
    try:
        from rpi_ws281x import PixelStrip, Color, ws
        
        print("Testing RGB Color Mapping...")
        print("Configuration:")
        print(f"  GPIO: {LED_PIN}, Count: {LED_COUNT}, Freq: {LED_FREQ_HZ}")
        
        # Test with RGB type first
        strip = PixelStrip(LED_COUNT, LED_PIN, LED_FREQ_HZ, LED_DMA, LED_INVERT, LED_BRIGHTNESS, LED_CHANNEL, ws.WS2811_STRIP_RGB)
        strip.begin()
        
        colors = [
            ("PURE RED", Color(255, 0, 0)),
            ("PURE GREEN", Color(0, 255, 0)),
            ("PURE BLUE", Color(0, 0, 255)),
            ("OFF", Color(0, 0, 0))
        ]
        
        for name, color in colors:
            print(f"Setting software to {name}...")
            for i in range(strip.numPixels()):
                strip.setPixelColor(i, color)
            strip.show()
            time.sleep(3)
            
        print("Test finished.")
        
    except ImportError:
        print("Error: rpi_ws281x not installed.")
    except Exception as e:
        print(f"Error: {e}")

if __name__ == "__main__":
    if os.getuid() != 0:
        print("This script must be run as root (sudo) to access /dev/mem")
        sys.exit(1)
    test_colors()
