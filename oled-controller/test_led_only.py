import time
import sys

def test_rgb():
    print("Testing ONLY the RGB LEDs via rpi_ws281x on GPIO 18...")
    print("If it stays white, the OS audio driver is likely interfering with PWM.")
    
    try:
        from rpi_ws281x import PixelStrip, Color
        
        # ZP-0129 standard configuration
        LED_COUNT = 4      
        LED_PIN = 18      
        LED_FREQ_HZ = 800000 
        LED_DMA = 10      
        LED_BRIGHTNESS = 255     
        LED_INVERT = False   
        LED_CHANNEL = 0       
        
        strip = PixelStrip(LED_COUNT, LED_PIN, LED_FREQ_HZ, LED_DMA, LED_INVERT, LED_BRIGHTNESS, LED_CHANNEL)
        strip.begin()
        
        print("Turning LEDs RED...")
        for i in range(strip.numPixels()):
            strip.setPixelColor(i, Color(255, 0, 0)) # Red (or Green depending on GRB/RGB)
        strip.show()
        time.sleep(2)
        
        print("Turning LEDs BLUE...")
        for i in range(strip.numPixels()):
            strip.setPixelColor(i, Color(0, 0, 255))
        strip.show()
        time.sleep(2)
        
        print("Turning LEDs OFF...")
        for i in range(strip.numPixels()):
            strip.setPixelColor(i, Color(0, 0, 0))
        strip.show()
        
        print("Test Complete.")
        
    except Exception as e:
        print(f"Error: {e}")

if __name__ == '__main__':
    test_rgb()
