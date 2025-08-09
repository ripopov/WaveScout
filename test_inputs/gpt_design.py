import argparse
import math
from datetime import datetime
from typing import List, Tuple, Dict

# VCD identifier encoding copied/adapted from signal_gen.py

def encode_id(n: int) -> str:
    """Encode a number as a VCD identifier using printable ASCII characters."""
    chars = "!\"#$%&'()*+,-./0123456789:;<=>?@ABCDEFGHIJKLMNOPQRSTUVWXYZ[\\]^_`abcdefghijklmnopqrstuvwxyz{|}~"
    if n == 0:
        return chars[0]
    result = ""
    base = len(chars)
    while n > 0:
        result = chars[n % base] + result
        n //= base
    return result


class VCDDesignGenerator:
    """
    Generates a large hierarchical VCD for benchmarking waveform viewers.

    Requirements implemented:
    - 10 levels of nested scopes (a single chain of nested modules).
    - At each level: include clocks of differing frequencies, digital signals, buses of various sizes, and real (analog) signals.
    - Total variable count across all scopes: 1,000,000.
    - No aliases (we keep all unique; aliasing would be allowed for clocks, but not required).
    - Command-line options:
        - -o / --output: output filename (default: gpt_design.vcd)
        - -clocks: number of clock signals to generate (default: 10000)
    - Base clock frequency reference: 1 GHz (period 1000 ps). Generated clocks vary relative to this.

    The generator writes:
    - Standard VCD header with timescale 1ps.
    - 10 nested scopes under a top module.
    - Variable declarations to reach exactly 1,000,000 variables including clocks.
    - $dumpvars with initial values.
    - Minimal activity: for clocks, two edges are emitted (rise/fall) at their first half/whole periods to reflect different frequencies.
    """

    TARGET_VARIABLES = 1_000_000
    LEVELS = 10
    SCOPE_VAR_LIMIT = 1000
    BASE_FREQ_HZ = 1_000_000_000  # 1 GHz
    BASE_PERIOD_PS = 1_000  # 1 ns = 1000 ps

    def __init__(self, output: str = "gpt_design.vcd", clocks: int = 10_000):
        self.output = output
        self.clock_count = int(clocks)
        self.file = None
        self.var_index = 0  # For generating unique VCD identifiers
        # Minimal metadata storage
        self.all_vars: List[Tuple[str, str, int]] = []  # (id, var_type, bitwidth)
        self.clock_events: List[Tuple[int, str, int]] = []  # (time_ps, id, new_val)

    # --------------------- low-level I/O ---------------------
    def open(self):
        self.file = open(self.output, "w", buffering=1024 * 1024)

    def close(self):
        if self.file:
            self.file.close()
            self.file = None

    def w(self, line: str = ""):
        self.file.write(line + "\n")

    # --------------------- header ---------------------
    def write_header(self):
        self.w("$date")
        self.w(f"    {datetime.now().strftime('%a %b %d %H:%M:%S %Y')}")
        self.w("$end")
        self.w("$version")
        self.w("    WaveScout gpt_design.py")
        self.w("$end")
        self.w("$timescale")
        self.w("    1ps")
        self.w("$end")

    # --------------------- declarations ---------------------
    def new_var(self, var_type: str, bitwidth: int, name: str) -> str:
        vid = encode_id(self.var_index)
        self.var_index += 1
        self.w(f"$var {var_type} {bitwidth} {vid} {name} $end")
        # store minimal metadata for dumpvars
        self.all_vars.append((vid, var_type, bitwidth))
        return vid

    def add_level_signals(self, level: int, approx_per_level: int, clocks_for_level: int, clock_base_index: int) -> int:
        """Add a mix of signals at this level without exceeding SCOPE_VAR_LIMIT in any scope.
        Returns next clock base index after adding level clocks.
        """
        # Define small fixed variety
        varieties = [
            ("wire", 1, 16),        # 16 single-bit wires
            ("reg", 1, 16),         # 16 single-bit regs
            ("reg", 8, 8),          # 8 x 8-bit buses
            ("reg", 16, 8),         # 8 x 16-bit buses
            ("reg", 32, 4),         # 4 x 32-bit buses
            ("reg", 64, 4),         # 4 x 64-bit buses
            ("integer", 32, 8),     # 8 integers
            ("real", 64, 8),        # 8 real signals
        ]
        base_variety_count = sum(c for _, _, c in varieties)

        # How many filler vars (1-bit regs) do we need to hit approx_per_level?
        fill_to_go = max(0, approx_per_level - (base_variety_count + clocks_for_level))

        # If everything fits, place directly in this scope to avoid extra depth
        if approx_per_level <= self.SCOPE_VAR_LIMIT:
            # Emit varieties
            for vtype, bw, count in varieties:
                for i in range(count):
                    self.new_var(vtype, bw, f"lvl{level}_{vtype}{bw}_{i}")
            # Emit clocks
            for i in range(clocks_for_level):
                clk_global_idx = clock_base_index + i
                vid = self.new_var("wire", 1, f"clk_l{level}_{clk_global_idx}")
                factor = (level + 1) * ((clk_global_idx % 16) + 1)
                period_ps = self.BASE_PERIOD_PS * factor
                half_ps = period_ps // 2
                self.clock_events.append((half_ps, vid, 1))
                self.clock_events.append((period_ps, vid, 0))
            # Emit fillers
            for i in range(fill_to_go):
                self.new_var("reg", 1, f"lvl{level}_bit_{i}")
            return clock_base_index + clocks_for_level

        # Otherwise, shard into subscopes B0, B1, ... to keep <= SCOPE_VAR_LIMIT per scope
        bucket_idx = -1
        bucket_count = 0
        buckets_opened = 0

        def open_bucket():
            nonlocal bucket_idx, bucket_count, buckets_opened
            bucket_idx += 1
            self.w(f"$scope module B{bucket_idx} $end")
            buckets_opened += 1
            bucket_count = 0

        def ensure_bucket_space(n_new: int = 1):
            # Open new bucket if adding n_new would exceed limit
            nonlocal bucket_count
            if bucket_idx == -1 or (bucket_count + n_new) > self.SCOPE_VAR_LIMIT:
                # Close previous bucket if any
                if bucket_idx >= 0:
                    self.w("$upscope $end")
                open_bucket()

        def add_var(vtype: str, bw: int, name: str) -> str:
            nonlocal bucket_count
            ensure_bucket_space(1)
            vid_local = self.new_var(vtype, bw, name)
            bucket_count += 1
            return vid_local

        # Emit varieties (streamed across buckets)
        for vtype, bw, count in varieties:
            for i in range(count):
                add_var(vtype, bw, f"lvl{level}_{vtype}{bw}_{i}")

        # Emit clocks (streamed across buckets)
        for i in range(clocks_for_level):
            clk_global_idx = clock_base_index + i
            vid = add_var("wire", 1, f"clk_l{level}_{clk_global_idx}")
            factor = (level + 1) * ((clk_global_idx % 16) + 1)
            period_ps = self.BASE_PERIOD_PS * factor
            half_ps = period_ps // 2
            self.clock_events.append((half_ps, vid, 1))
            self.clock_events.append((period_ps, vid, 0))

        # Emit fillers (streamed across buckets)
        for i in range(fill_to_go):
            add_var("reg", 1, f"lvl{level}_bit_{i}")

        # Close the last opened bucket, if any
        if bucket_idx >= 0:
            self.w("$upscope $end")
        return clock_base_index + clocks_for_level

    def write_design(self):
        self.w("$scope module top $end")
        # Decide distribution of variables
        total_target = self.TARGET_VARIABLES
        clocks_total = self.clock_count
        # Reserve a modest number per non-deep level for variety
        approx_small_per_level = 64 + 16 + 16 + 8 + 8 + 8 + 8 + 8  # from varieties above = 136
        # plus at least one clock per level later when distributing
        # Compute how many variables are left after: 10 * approx_small_per_level + clocks
        overhead_vars = self.LEVELS * approx_small_per_level + clocks_total
        # Ensure positive remainder
        remainder = max(0, total_target - overhead_vars)
        # We'll put essentially all remainder at the deepest level as extra 1-bit regs to hit target precisely
        # Distribute clocks roughly evenly per level
        clocks_per_level_base = clocks_total // self.LEVELS
        clocks_remainder = clocks_total % self.LEVELS

        clock_base_index = 0
        for level in range(self.LEVELS):
            self.w(f"$scope module L{level} $end")
            # At each level add the small variety and some clocks
            c_for_level = clocks_per_level_base + (1 if level < clocks_remainder else 0)
            extra_fill = 0
            if level == self.LEVELS - 1:
                # place all remainder here
                extra_fill = remainder
            approx_for_this_level = approx_small_per_level + c_for_level + extra_fill
            clock_base_index = self.add_level_signals(level, approx_for_this_level, c_for_level, clock_base_index)
        # close all scopes
        for level in reversed(range(self.LEVELS)):
            self.w("$upscope $end")
        self.w("$enddefinitions $end")

    # --------------------- initial values and minimal activity ---------------------
    def write_initial_and_clocks(self):
        # Initial values
        self.w("#0")
        self.w("$dumpvars")
        for vid, vtype, bw in self.all_vars:
            if vtype == "real":
                self.w(f"r0 {vid}")
            elif bw == 1:
                self.w(f"0{vid}")
            else:
                # binary zero with at least 1 bit; VCD allows 'b0' without width, but to be safe we can just print b0
                # Not all viewers require zero-padded width during dumpvars
                self.w(f"b0 {vid}")
        self.w("$end")
        # Clock events: sort and emit time-ordered changes
        if not self.clock_events:
            return
        self.clock_events.sort(key=lambda e: e[0])
        current_time = -1
        for t, vid, val in self.clock_events:
            if t != current_time:
                self.w(f"#{t}")
                current_time = t
            self.w(f"{val}{vid}")

    # --------------------- main API ---------------------
    def generate(self):
        try:
            self.open()
            self.write_header()
            self.write_design()
            self.write_initial_and_clocks()
        finally:
            self.close()


def parse_args():
    ap = argparse.ArgumentParser(description="Generate a large hierarchical VCD for benchmarking.")
    ap.add_argument("-o", "--output", default="design-gpt5.vcd", help="Output VCD filename (default: design.vcd)")
    ap.add_argument("-clocks", type=int, default=10_000, help="Number of clock signals to generate (default: 10000)")
    return ap.parse_args()


def main():
    args = parse_args()
    gen = VCDDesignGenerator(output=args.output, clocks=args.clocks)
    gen.generate()
    print(f"Generated VCD: {args.output}")
    print(f"Total variables (declared): {gen.var_index}")
    print(f"Clocks generated: {gen.clock_count}")
    print("Hierarchy levels: 10")
    print("Timescale: 1ps; Base clock: 1 GHz")


if __name__ == "__main__":
    main()
