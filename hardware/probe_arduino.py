import serial
import time

def probe():
    print("Opening COM5 at 115200 baud...")
    try:
        ser = serial.Serial('COM5', 115200, timeout=1.0)
        time.sleep(0.1)
        ser.reset_input_buffer()
        ser.reset_output_buffer()
        print("[+] COM5 Opened successfully!")
        
        # Test sending command
        print("[*] Sending 's' command to start tick stream...")
        ser.write(b's')
        time.sleep(0.5)
        
        incoming = ser.read(ser.in_waiting or 100)
        print(f"[+] Received {len(incoming)} bytes from COM5")
        if incoming:
            print(f"    Raw bytes: {incoming.hex()[:80]}")
        else:
            print("    [Note: Arduino may be idling or waiting for sketch upload]")
        ser.close()
    except Exception as e:
        print(f"[-] COM5 probe error: {e}")

if __name__ == "__main__":
    probe()
