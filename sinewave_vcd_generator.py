#!/usr/bin/env python3
"""
Generate a VCD file with 10 sinewave signals of different frequency and amplitude.
Based on the VCD format understanding from jtag.vcd and existing vcd_generator.py.
"""

import math
import sys
from datetime import datetime


def encode_id(n):
    """Encode a number as a VCD identifier using printable ASCII characters."""
    chars = "!\"#$%&'()*+,-./0123456789:;<=>?@ABCDEFGHIJKLMNOPQRSTUVWXYZ[\\]^_`abcdefghijklmnopqrstuvwxyz{|}~"
    if n == 0:
        return chars[0]
    
    result = ""
    while n > 0:
        result = chars[n % len(chars)] + result
        n //= len(chars)
    return result


class VCDGenerator:
    def __init__(self, filename="sinewave_signals.vcd"):
        self.filename = filename
        self.file = None
        self.time_ps = 0
        self.signals = []
        
    def open_file(self):
        """Open the VCD file for writing."""
        self.file = open(self.filename, 'w')
        
    def close_file(self):
        """Close the VCD file."""
        if self.file:
            self.file.close()
            
    def write_line(self, line=""):
        """Write a line to the VCD file."""
        self.file.write(line + "\n")
        
    def write_header(self):
        """Write the VCD header section."""
        self.write_line("$date")
        self.write_line(f"    {datetime.now().strftime('%a %b %d %H:%M:%S %Y')}")
        self.write_line("$end")
        self.write_line("$version")
        self.write_line("    Python Sinewave VCD Generator")
        self.write_line("$end")
        self.write_line("$timescale")
        self.write_line("    1ps")
        self.write_line("$end")
        
    def define_signals(self):
        """Define 10 sinewave signals with different frequencies and amplitudes."""
        self.write_line("$scope module top $end")
        
        # Define 10 signals with different characteristics
        signal_configs = [
            {"name": "sine_1khz", "freq": 1000, "amp": 1.0, "bitwidth": 8},
            {"name": "sine_5khz", "freq": 5000, "amp": 0.8, "bitwidth": 8},
            {"name": "sine_10khz", "freq": 10000, "amp": 0.9, "bitwidth": 8},
            {"name": "sine_25khz", "freq": 25000, "amp": 0.7, "bitwidth": 8},
            {"name": "sine_50khz", "freq": 50000, "amp": 0.6, "bitwidth": 8},
            {"name": "sine_100khz", "freq": 100000, "amp": 0.85, "bitwidth": 8},
            {"name": "sine_250khz", "freq": 250000, "amp": 0.75, "bitwidth": 8},
            {"name": "sine_500khz", "freq": 500000, "amp": 0.95, "bitwidth": 8},
            {"name": "sine_1mhz", "freq": 1000000, "amp": 0.65, "bitwidth": 8},
            {"name": "sine_2mhz", "freq": 2000000, "amp": 0.55, "bitwidth": 8},
        ]
        
        for i, config in enumerate(signal_configs):
            signal_id = encode_id(i)
            self.write_line(f"$var wire {config['bitwidth']} {signal_id} {config['name']} $end")
            
            # Store signal info for simulation
            self.signals.append({
                "id": signal_id,
                "name": config["name"],
                "freq": config["freq"],
                "amp": config["amp"],
                "bitwidth": config["bitwidth"],
                "phase": i * math.pi / 5,  # Different phase for each signal
                "last_value": None
            })
            
        self.write_line("$upscope $end")
        self.write_line("$enddefinitions $end")
        
    def calculate_signal_value(self, signal, time_sec):
        """Calculate the quantized value of a sine signal at a given time."""
        # Calculate sine value (-1 to 1)
        sine_val = signal["amp"] * math.sin(2 * math.pi * signal["freq"] * time_sec + signal["phase"])
        
        # Normalize to 0-1 range
        normalized = (sine_val + 1) / 2
        
        # Quantize to digital value based on bit width
        max_val = (2 ** signal["bitwidth"]) - 1
        quantized = int(normalized * max_val)
        
        return quantized
        
    def write_initial_values(self):
        """Write initial signal values at time 0."""
        self.write_line("#0")
        self.write_line("$dumpvars")
        
        for signal in self.signals:
            value = self.calculate_signal_value(signal, 0.0)
            signal["last_value"] = value
            
            if signal["bitwidth"] == 1:
                self.write_line(f"{value}{signal['id']}")
            else:
                bin_str = format(value, "b")
                self.write_line(f"b{bin_str} {signal['id']}")
                
        self.write_line("$end")
        
    def simulate(self, duration_ms=1.0, sample_interval_ps=1000):
        """Simulate the signals over time and write value changes."""
        duration_ps = int(duration_ms * 1e9)  # Convert ms to ps
        
        current_time = 0
        while current_time <= duration_ps:
            time_sec = current_time * 1e-12  # Convert ps to seconds
            
            # Check if any signal values have changed
            changes = []
            for signal in self.signals:
                new_value = self.calculate_signal_value(signal, time_sec)
                if new_value != signal["last_value"]:
                    signal["last_value"] = new_value
                    changes.append((signal, new_value))
            
            # Write time stamp and changes if any occurred
            if changes:
                self.write_line(f"#{current_time}")
                for signal, value in changes:
                    if signal["bitwidth"] == 1:
                        self.write_line(f"{value}{signal['id']}")
                    else:
                        bin_str = format(value, "b")
                        self.write_line(f"b{bin_str} {signal['id']}")
            
            current_time += sample_interval_ps
            
    def generate(self, duration_ms=1.0, sample_interval_ps=1000):
        """Generate the complete VCD file."""
        try:
            self.open_file()
            self.write_header()
            self.define_signals()
            self.write_initial_values()
            self.simulate(duration_ms, sample_interval_ps)
            print(f"VCD file '{self.filename}' generated successfully!")
            print(f"Contains 10 sinewave signals with frequencies from 1kHz to 2MHz")
            print(f"Simulation duration: {duration_ms}ms")
            print(f"Sample interval: {sample_interval_ps}ps")
        finally:
            self.close_file()


def main():
    """Main function to generate the VCD file."""
    if len(sys.argv) > 1:
        filename = sys.argv[1]
    else:
        filename = "sinewave_signals.vcd"
        
    generator = VCDGenerator(filename)
    
    # Generate 1ms of simulation with 1ns sampling
    generator.generate(duration_ms=1.0, sample_interval_ps=1000)


if __name__ == "__main__":
    main()