#!/usr/bin/env python3
"""
Generate a VCD file with 10 sinewave signals of different frequency and amplitude.
Based on the VCD format understanding from jtag.vcd and existing vcd_generator.py.
"""

import math
import sys
import struct
from datetime import datetime


def float_to_e4m3(value):
    """Convert a float to E4M3 FP8 format (8-bit reg)."""
    if value == 0.0:
        return 0
    if math.isnan(value):
        return 0x7F  # NaN representation
    if math.isinf(value):
        return 0x78 if value > 0 else 0xF8  # +/- Inf

    # Get IEEE 754 representation
    packed = struct.pack('!f', float(value))
    ieee_bits = struct.unpack('!I', packed)[0]

    # Extract sign, exponent, mantissa
    sign = (ieee_bits >> 31) & 1
    exp = (ieee_bits >> 23) & 0xFF
    mantissa = ieee_bits & 0x7FFFFF

    # Convert to E4M3: 1 sign + 4 exponent + 3 mantissa bits
    # Bias: E4M3 uses bias of 7 (2^3 - 1), IEEE uses 127
    if exp == 0:
        # Subnormal or zero
        return sign << 7

    # Adjust exponent bias (127 -> 7)
    new_exp = exp - 127 + 7

    # Clamp exponent to 4-bit range (0-15)
    if new_exp <= 0:
        return sign << 7  # Underflow to zero
    elif new_exp >= 15:
        return (sign << 7) | 0x78  # Overflow to max/inf

    # Extract top 3 bits of mantissa
    new_mantissa = (mantissa >> 20) & 0x7

    return (sign << 7) | (new_exp << 3) | new_mantissa


def float_to_e5m2(value):
    """Convert a float to E5M2 FP8 format (8-bit reg)."""
    if value == 0.0:
        return 0
    if math.isnan(value):
        return 0x7F  # NaN representation
    if math.isinf(value):
        return 0x7C if value > 0 else 0xFC  # +/- Inf

    # Get IEEE 754 representation
    packed = struct.pack('!f', float(value))
    ieee_bits = struct.unpack('!I', packed)[0]

    # Extract sign, exponent, mantissa
    sign = (ieee_bits >> 31) & 1
    exp = (ieee_bits >> 23) & 0xFF
    mantissa = ieee_bits & 0x7FFFFF

    # Convert to E5M2: 1 sign + 5 exponent + 2 mantissa bits
    # Bias: E5M2 uses bias of 15 (2^4 - 1), IEEE uses 127
    if exp == 0:
        # Subnormal or zero
        return sign << 7

    # Adjust exponent bias (127 -> 15)
    new_exp = exp - 127 + 15

    # Clamp exponent to 5-bit range (0-31)
    if new_exp <= 0:
        return sign << 7  # Underflow to zero
    elif new_exp >= 31:
        return (sign << 7) | 0x7C  # Overflow to max/inf

    # Extract top 2 bits of mantissa
    new_mantissa = (mantissa >> 21) & 0x3

    return (sign << 7) | (new_exp << 2) | new_mantissa


def float_to_bf16(value):
    """Convert a float to BF16 (bfloat16) format (16-bit reg)."""
    if value == 0.0:
        return 0
    if math.isnan(value):
        return 0x7FC0  # NaN representation
    if math.isinf(value):
        return 0x7F80 if value > 0 else 0xFF80  # +/- Inf

    # Get IEEE 754 representation
    packed = struct.pack('!f', float(value))
    ieee_bits = struct.unpack('!I', packed)[0]

    # BF16 is simply the upper 16 bits of IEEE 754 FP32
    # 1 sign + 8 exponent + 7 mantissa bits
    bf16_bits = ieee_bits >> 16

    return bf16_bits


def float_to_ieee_fp16(value):
    """Convert a float to IEEE FP16 half precision format (16-bit reg)."""
    if value == 0.0:
        return 0
    if math.isnan(value):
        return 0x7E00  # NaN representation
    if math.isinf(value):
        return 0x7C00 if value > 0 else 0xFC00  # +/- Inf

    # Get IEEE 754 representation
    packed = struct.pack('!f', float(value))
    ieee_bits = struct.unpack('!I', packed)[0]

    # Extract sign, exponent, mantissa from FP32
    sign = (ieee_bits >> 31) & 1
    exp = (ieee_bits >> 23) & 0xFF
    mantissa = ieee_bits & 0x7FFFFF

    # Convert to FP16: 1 sign + 5 exponent + 10 mantissa bits
    # Bias: FP16 uses bias of 15, IEEE FP32 uses 127
    if exp == 0:
        # Subnormal or zero
        return sign << 15

    # Adjust exponent bias (127 -> 15)
    new_exp = exp - 127 + 15

    # Handle overflow/underflow
    if new_exp <= 0:
        # Underflow - could implement subnormal handling, but for simplicity use zero
        return sign << 15
    elif new_exp >= 31:
        # Overflow to infinity
        return (sign << 15) | 0x7C00

    # Extract top 10 bits of mantissa
    new_mantissa = (mantissa >> 13) & 0x3FF

    return (sign << 15) | (new_exp << 10) | new_mantissa


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

        # Define 10 signals with different characteristics plus clock counter
        # sampling_period: how often signal value is dumped (in units of sample_interval_ps)
        # 1 = dump every sample_interval_ps, 3 = dump every 3 sample_interval_ps, etc.
        # signal_type: reg, real, integer, wire
        # amp_range: [min, max] amplitude range for the signal
        signal_configs = [
            {"name": "clk_cnt", "freq": 0, "amp_range": [0, 0], "bitwidth": 32, "sampling_period": 1,
             "var_type": "integer", "wave_type": "clock", "is_clock_counter": True},
            {"name": "sine_1khz", "freq": 1000, "amp_range": [-1, 1], "bitwidth": 64, "sampling_period": 1, "var_type": "real", "wave_type": "sine"},
            {"name": "sine_5khz", "freq": 5000, "amp_range": [0, 255], "bitwidth": 8, "sampling_period": 2, "var_type": "reg", "wave_type": "sine"},
            {"name": "sine_10khz", "freq": 10000, "amp_range": [-100, 100], "bitwidth": 8, "sampling_period": 3, "var_type": "integer", "wave_type": "sine"},
            {"name": "sine_25khz", "freq": 25000, "amp_range": [0, 1.5], "bitwidth": 64, "sampling_period": 1, "var_type": "real", "wave_type": "sine"},
            {"name": "sine_50khz", "freq": 50000, "amp_range": [0, 1000], "bitwidth": 16, "sampling_period": 4, "var_type": "reg", "wave_type": "sine"},
            {"name": "sine_100khz", "freq": 100000, "amp_range": [-500, 500], "bitwidth": 16, "sampling_period": 2, "var_type": "integer", "wave_type": "sine"},
            {"name": "sine_250khz", "freq": 250000, "amp_range": [0, 1], "bitwidth": 1, "sampling_period": 5, "var_type": "wire", "wave_type": "sine"},
            {"name": "sine_500khz", "freq": 500000, "amp_range": [-2.5, 2.5], "bitwidth": 64, "sampling_period": 1, "var_type": "real", "wave_type": "sine"},
            {"name": "sine_1mhz", "freq": 1000000, "amp_range": [0, 127], "bitwidth": 8, "sampling_period": 3, "var_type": "reg", "wave_type": "sine"},
            {"name": "sine_2mhz", "freq": 2000000, "amp_range": [-1000, 1000], "bitwidth": 16, "sampling_period": 6, "var_type": "integer", "wave_type": "sine"},
            {"name": "triangle_10khz", "freq": 10000, "amp_range": [-1, 1], "bitwidth": 64, "sampling_period": 1, "var_type": "real", "wave_type": "triangle"},
            {"name": "pulse_5khz", "freq": 5000, "amp_range": [-2, 2], "bitwidth": 64, "sampling_period": 1, "var_type": "real", "wave_type": "pulse"},
            {"name": "sine_4state_20khz", "freq": 20000, "amp_range": [0, 255], "bitwidth": 8, "sampling_period": 1, "var_type": "reg", "wave_type": "sine_4state"},
            {"name": "sine_e4m3_15khz", "freq": 15000, "amp_range": [-1.5, 1.5], "bitwidth": 8, "sampling_period": 2, "var_type": "E4M3", "wave_type": "sine"},
            {"name": "sine_e5m2_30khz", "freq": 30000, "amp_range": [-2.0, 2.0], "bitwidth": 8, "sampling_period": 3, "var_type": "E5M2", "wave_type": "sine"},
            {"name": "sine_bf16_12khz", "freq": 12000, "amp_range": [-3.0, 3.0], "bitwidth": 16, "sampling_period": 2, "var_type": "BF16", "wave_type": "sine"},
            {"name": "sine_fp16_35khz", "freq": 35000, "amp_range": [-1.8, 1.8], "bitwidth": 16, "sampling_period": 4, "var_type": "IEEE_FP16", "wave_type": "sine"},
            {"name": "event_sine_sweep", "freq": 100, "amp_range": [0, 0], "bitwidth": 1, "sampling_period": 1,
             "var_type": "event", "wave_type": "event", "min_period": 100, "max_period": 10000},
        ]

        for i, config in enumerate(signal_configs):
            signal_id = encode_id(i)
            # Map FP8 and FP16 types to reg for VCD output, keep event as event
            if config['var_type'] in ["E4M3", "E5M2", "BF16", "IEEE_FP16"]:
                vcd_var_type = "reg"
            else:
                vcd_var_type = config['var_type']
            self.write_line(f"$var {vcd_var_type} {config['bitwidth']} {signal_id} {config['name']} $end")

            # Store signal info for simulation
            signal_info = {
                "id": signal_id,
                "name": config["name"],
                "freq": config["freq"],
                "amp_range": config["amp_range"],
                "var_type": config["var_type"],
                "bitwidth": config["bitwidth"],
                "wave_type": config["wave_type"],
                "phase": i * math.pi / 5,  # Different phase for each signal
                "sampling_period": config["sampling_period"],
                "next_sample_time": 0,  # Initialize to 0 so all signals are sampled initially
                "last_value": None
            }

            # Add clock counter specific fields
            if config.get("is_clock_counter", False):
                signal_info["is_clock_counter"] = True
                signal_info["counter_value"] = 0

            # Add event specific fields
            if config.get("var_type") == "event":
                signal_info["min_period"] = config.get("min_period", 100)
                signal_info["max_period"] = config.get("max_period", 10000)
                signal_info["last_event_time"] = 0

            self.signals.append(signal_info)

        self.write_line("$upscope $end")
        self.write_line("$enddefinitions $end")

    def calculate_signal_value(self, signal, time_sec):
        """Calculate the value of a signal at a given time based on its type and range."""
        # Handle clock counter specially
        if signal.get("is_clock_counter", False):
            return signal["counter_value"]

        # Handle event signals
        if signal["var_type"] == "event":
            # For events, we need to determine if an event should fire at this time
            # Calculate the current sampling period based on sine wave
            sine_val = math.sin(2 * math.pi * signal["freq"] * time_sec + signal["phase"])
            # Map sine value (-1 to 1) to period range (min_period to max_period)
            current_period_ps = signal["min_period"] + (sine_val + 1) / 2 * (
                        signal["max_period"] - signal["min_period"])

            # Check if enough time has passed since last event
            time_ps = int(time_sec * 1e12)  # Convert to ps
            if time_ps - signal["last_event_time"] >= current_period_ps:
                signal["last_event_time"] = time_ps
                return 1  # Event fires
            else:
                return None  # No event

        # Calculate waveform value based on signal type
        if signal["wave_type"] == "sine":
            # Calculate sine value (-1 to 1)
            wave_val = math.sin(2 * math.pi * signal["freq"] * time_sec + signal["phase"])
        elif signal["wave_type"] == "sine_4state":
            # Calculate which period we're in
            period_time = 1.0 / signal["freq"]
            time_with_phase = time_sec + signal["phase"] / (2 * math.pi * signal["freq"])
            current_period = int(time_with_phase / period_time)

            # Every 4th period (periods 3, 7, 11, 15, etc.) return special value
            if current_period % 4 == 3:
                # Alternate between 'z' and 'x' based on which 4th period we're in
                # Period 3, 11, 19, etc. -> 'z'
                # Period 7, 15, 23, etc. -> 'x'
                period_group = current_period // 4
                return 'z' if (period_group % 2 == 0) else 'x'
            else:
                # Normal sine wave for periods 0, 1, 2, 4, 5, 6, etc.
                wave_val = math.sin(2 * math.pi * signal["freq"] * time_sec + signal["phase"])
        elif signal["wave_type"] == "triangle":
            # Calculate triangular wave value (-1 to 1)
            # Use sawtooth function: 2 * (t * freq - floor(t * freq + 0.5))
            t_normalized = (signal["freq"] * time_sec + signal["phase"] / (2 * math.pi)) % 1
            if t_normalized < 0.5:
                wave_val = 4 * t_normalized - 1  # Rising edge: -1 to 1
            else:
                wave_val = 3 - 4 * t_normalized  # Falling edge: 1 to -1
        elif signal["wave_type"] == "pulse":
            # Calculate pulse wave with high-frequency noise and periodic high amplitude pulses
            # High-frequency noise component (much higher frequency than the main pulse)
            noise_freq = 1e6  # 1 MHz noise frequency
            noise_amplitude = 0.1  # Low amplitude noise (10% of full scale)
            noise_val = noise_amplitude * math.sin(2 * math.pi * noise_freq * time_sec + signal["phase"])

            # Pulse component based on signal frequency
            pulse_period = 1.0 / signal["freq"]  # Period in seconds
            time_in_period = (time_sec + signal["phase"] / (2 * math.pi * signal["freq"])) % pulse_period

            # Pulse duration is 2 sample_interval_ps, but we need to convert to seconds
            # Since we don't have direct access to sample_interval_ps here, we'll use a small fraction of the period
            pulse_duration = pulse_period * 0.02  # 2% of the period as pulse duration

            if time_in_period < pulse_duration:
                # During pulse: high amplitude (full scale)
                pulse_val = 1.0
            else:
                # Outside pulse: low amplitude
                pulse_val = 0.0

            # Combine noise and pulse
            wave_val = noise_val + pulse_val
            # Clamp to [-1, 1] range
            wave_val = max(-1, min(1, wave_val))
        else:
            # Default to sine wave for unknown types
            wave_val = math.sin(2 * math.pi * signal["freq"] * time_sec + signal["phase"])

        # For sine_4state, if we're returning a special state, do it now
        if signal["wave_type"] == "sine_4state" and isinstance(wave_val, str):
            return wave_val

        # Map wave value to the specified amplitude range
        amp_min, amp_max = signal["amp_range"]
        mapped_val = amp_min + (wave_val + 1) / 2 * (amp_max - amp_min)

        # Handle different signal types
        if signal["var_type"] == "real":
            # Real numbers - return as float, will be formatted later
            return mapped_val
        elif signal["var_type"] == "E4M3":
            # E4M3 FP8 encoding
            return float_to_e4m3(mapped_val)
        elif signal["var_type"] == "E5M2":
            # E5M2 FP8 encoding
            return float_to_e5m2(mapped_val)
        elif signal["var_type"] == "BF16":
            # BF16 encoding
            return float_to_bf16(mapped_val)
        elif signal["var_type"] == "IEEE_FP16":
            # IEEE FP16 encoding
            return float_to_ieee_fp16(mapped_val)
        else:
            # For non-real types (reg, integer, wire), round to nearest integer
            rounded_val = round(mapped_val)

            # For single-bit signals, clamp to 0 or 1
            if signal["bitwidth"] == 1:
                return 1 if rounded_val > 0 else 0

            # For multi-bit signals, ensure value fits in the bit width
            if signal["var_type"] in ["reg", "wire"]:
                # Unsigned values
                max_val = (2 ** signal["bitwidth"]) - 1
                return max(0, min(rounded_val, max_val))
            else:  # integer type
                # Signed values
                max_val = (2 ** (signal["bitwidth"] - 1)) - 1
                min_val = -(2 ** (signal["bitwidth"] - 1))
                return max(min_val, min(rounded_val, max_val))

        return rounded_val

    def write_initial_values(self):
        """Write initial signal values at time 0."""
        self.write_line("#0")
        self.write_line("$dumpvars")

        for signal in self.signals:
            value = self.calculate_signal_value(signal, 0.0)
            signal["last_value"] = value

            # Skip initial value for event signals (they don't have initial values)
            if signal["var_type"] == "event":
                continue

            # Format value based on signal type
            if isinstance(value, str) and value in ['z', 'x']:
                # Handle Z and X states for multi-bit signals
                self.write_line(f"b{value} {signal['id']}")
            elif signal["var_type"] == "real":
                # Real numbers use 'r' prefix and %.16g format
                self.write_line(f"r{value:.16g} {signal['id']}")
            elif signal["var_type"] in ["E4M3", "E5M2"]:
                # FP8 types - dump as 8-bit binary
                bin_str = format(int(value), "08b")
                self.write_line(f"b{bin_str} {signal['id']}")
            elif signal["var_type"] in ["BF16", "IEEE_FP16"]:
                # FP16 types - dump as 16-bit binary
                bin_str = format(int(value), "016b")
                self.write_line(f"b{bin_str} {signal['id']}")
            elif signal["bitwidth"] == 1:
                # Single bit signals
                self.write_line(f"{int(value)}{signal['id']}")
            else:
                # Multi-bit integer signals use binary format
                if signal["var_type"] == "integer" and value < 0:
                    # For negative integers, use two's complement
                    unsigned_val = (1 << signal["bitwidth"]) + int(value)
                    bin_str = format(unsigned_val, f"0{signal['bitwidth']}b")
                else:
                    bin_str = format(int(value), "b")
                self.write_line(f"b{bin_str} {signal['id']}")

        self.write_line("$end")

    def simulate(self, duration_ms=1.0, sample_interval_ps=1000):
        """Simulate the signals over time and write value changes."""
        duration_ps = int(duration_ms * 1e9)  # Convert ms to ps

        current_time = 0
        sample_count = 0
        while current_time <= duration_ps:
            time_sec = current_time * 1e-12  # Convert ps to seconds

            # Increment clock counter on each sample
            for signal in self.signals:
                if signal.get("is_clock_counter", False):
                    signal["counter_value"] = sample_count

            # Check signals that should be sampled at this time
            changes = []
            for signal in self.signals:
                # Only sample this signal if it's time to do so
                if current_time >= signal["next_sample_time"]:
                    new_value = self.calculate_signal_value(signal, time_sec)
                    # For events, only record if the event fired (value is 1)
                    if signal["var_type"] == "event":
                        if new_value == 1:
                            changes.append((signal, new_value))
                    elif new_value != signal["last_value"]:
                        signal["last_value"] = new_value
                        changes.append((signal, new_value))

                    # Update next sample time for this signal
                    signal["next_sample_time"] = current_time + (signal["sampling_period"] * sample_interval_ps)

            # Write time stamp and changes if any occurred
            if changes:
                self.write_line(f"#{current_time}")
                for signal, value in changes:
                    # Format value based on signal type
                    if signal["var_type"] == "event":
                        # Events are always dumped as "1" followed by identifier
                        self.write_line(f"1{signal['id']}")
                    elif isinstance(value, str) and value in ['z', 'x']:
                        # Handle Z and X states for multi-bit signals
                        self.write_line(f"b{value} {signal['id']}")
                    elif signal["var_type"] == "real":
                        # Real numbers use 'r' prefix and %.16g format
                        self.write_line(f"r{value:.16g} {signal['id']}")
                    elif signal["var_type"] in ["E4M3", "E5M2"]:
                        # FP8 types - dump as 8-bit binary
                        bin_str = format(int(value), "08b")
                        self.write_line(f"b{bin_str} {signal['id']}")
                    elif signal["var_type"] in ["BF16", "IEEE_FP16"]:
                        # FP16 types - dump as 16-bit binary
                        bin_str = format(int(value), "016b")
                        self.write_line(f"b{bin_str} {signal['id']}")
                    elif signal["bitwidth"] == 1:
                        # Single bit signals
                        self.write_line(f"{int(value)}{signal['id']}")
                    else:
                        # Multi-bit integer signals use binary format
                        if signal["var_type"] == "integer" and value < 0:
                            # For negative integers, use two's complement
                            unsigned_val = (1 << signal["bitwidth"]) + int(value)
                            bin_str = format(unsigned_val, f"0{signal['bitwidth']}b")
                        else:
                            bin_str = format(int(value), "b")
                        self.write_line(f"b{bin_str} {signal['id']}")

            current_time += sample_interval_ps
            sample_count += 1

    def generate(self, duration_ms=1.0, sample_interval_ps=1000):
        """Generate the complete VCD file."""
        try:
            self.open_file()
            self.write_header()
            self.define_signals()
            self.write_initial_values()
            self.simulate(duration_ms, sample_interval_ps)
            print(f"VCD file '{self.filename}' generated successfully!")
            print(
                f"Contains 14 sinewave signals (including E4M3/E5M2 FP8 and BF16/IEEE_FP16), 1 triangular wave signal, 1 pulse signal, 1 sine_4state signal, and 1 event signal")
            print(f"Frequencies range from 1kHz to 2MHz")
            print(f"Simulation duration: {duration_ms}ms")
            print(f"Sample interval: {sample_interval_ps}ps")
        finally:
            self.close_file()


def main():
    """Main function to generate the VCD file."""
    if len(sys.argv) > 1:
        filename = sys.argv[1]
    else:
        filename = "analog_signals.vcd"

    generator = VCDGenerator(filename)

    # Generate 1ms of simulation with 1ns sampling
    generator.generate(duration_ms=1.0, sample_interval_ps=1000)


if __name__ == "__main__":
    main()