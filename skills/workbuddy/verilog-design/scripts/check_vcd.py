
import sys
from vcdvcd import VCDVCD

def check_vcd(vcd_file, signal_path, expected_values):
    vcd = VCDVCD(vcd_file)
    signal = vcd[signal_path]
    
    for time, expected in expected_values:
        actual = signal[time]
        if actual != expected:
            print(f"FAIL at t={time}: expected {expected}, got {actual}")
            return False
    
    print("PASS: All signal checks passed")
    return True

def get_transitions(vcd_file, signal_path):
    vcd = VCDVCD(vcd_file)
    signal = vcd[signal_path]
    return signal.tv  # List of (time, value) tuples

def verify_counter(vcd_file):
    vcd = VCDVCD(vcd_file)
    
    count_signal = None
    for path in vcd.signals:
        if "count" in path.lower():
            count_signal = vcd[path]
            break
    
    if not count_signal:
        print("ERROR: Counter signal not found")
        return False
    
    prev_val = -1
    for time, val in count_signal.tv:
        val_int = int(val, 2) if val.startswith('b') else int(val)
        if val_int != (prev_val + 1) % 16:  # Assuming 4-bit counter
            print(f"ERROR at t={time}: count jumped from {prev_val} to {val_int}")
            return False
        prev_val = val_int
    
    print("PASS: Counter verified")
    return True

if __name__ == "__main__":
    if len(sys.argv) < 2:
        print(f"Usage: {sys.argv[0]} <vcd_file> [signal_path] [time:value pairs...]")
        print(f"       {sys.argv[0]} counter.vcd  # Run counter verification")
        sys.exit(1)
    
    vcd_file = sys.argv[1]
    
    if len(sys.argv) == 2:
        success = verify_counter(vcd_file)
        sys.exit(0 if success else 1)
    
    signal_path = sys.argv[2]
    expected_values = []
    for pair in sys.argv[3:]:
        time, value = pair.split(':')
        expected_values.append((int(time), value))
    
    success = check_vcd(vcd_file, signal_path, expected_values)
    sys.exit(0 if success else 1)
