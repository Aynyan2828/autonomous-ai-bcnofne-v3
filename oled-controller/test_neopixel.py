import time
import board
import neopixel

def test_neopixel():
    print("Testing RGB LEDs using Adafruit NeoPixel library on GPIO 18...")
    
    try:
        # GPIO18 (board.D18)で4つのLEDを制御する設定
        pixels = neopixel.NeoPixel(board.D18, 4, brightness=1.0, auto_write=False, pixel_order=neopixel.RGB)
        
        print("Turning LEDs RED...")
        pixels.fill((255, 0, 0))
        pixels.show()
        time.sleep(2)
        
        print("Turning LEDs BLUE...")
        pixels.fill((0, 0, 255))
        pixels.show()
        time.sleep(2)
        
        print("Turning LEDs OFF...")
        pixels.fill((0, 0, 0))
        pixels.show()
        
        print("Test Complete.")
        
    except Exception as e:
        print(f"Error: {e}")

if __name__ == '__main__':
    test_neopixel()
