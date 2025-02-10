#!/usr/bin/env python3
"""
This module provides classes and functions to parse VCD (Value Change Dump)
files and dump signals
"""

import re
from math import ceil
from datetime import datetime


class VCDSignal:
    """
    Class representing a single signal extracted from a VCD file.
    Stores metadata (name, hierarchy, width) as well as time-stamped transitions.
    """
    def __init__(self, identifier, name, hierarchy, width=1):
        self.id = identifier                   # Unique VCD identifier (e.g., "!")
        self.name = name                       # Declared name (e.g., "BinCount")
        self.hierarchy = hierarchy[:]          # Copy of the hierarchy list
        self.fullname = '.'.join(hierarchy + [name])  # Full hierarchical name
        self.width = width                     # Bit width (default 1)
        self.transitions = []                  # List of (time, value) tuples
        self.aliases = [self.fullname]         # Alternative full names

        # Additional attributes (for display/waveform purposes)
        self.height_factor = 1
        self.rep_mode = "hex"                  # Options: "hex", "bin", or "decimal"
        self.analog_render = False


class VCDParser:
    """
    Optimized VCD file parser.

    Parameters:
        filename (str): Path to the VCD file.
        assume_sorted (bool): If True, the simulation time markers are assumed
                              to be in order, so per-signal sorting is skipped.
        full_memory (bool): If True, the entire file is loaded into memory
                            for faster processing. (Use False if memory is constrained.)
    """
    def __init__(self, filename, assume_sorted=True, full_memory=True):
        self.filename = filename
        self.signals = {}     # Map VCD IDs to VCDSignal objects
        self.hierarchy = {}   # Nested dict representing the design hierarchy
        self.timescale = None # Timescale string from the header (e.g., "1ns")
        self.metadata = {}    # Additional metadata (date, version, etc.)
        self.assume_sorted = assume_sorted
        self.full_memory = full_memory

    def parse(self):
        """
        Parse the VCD file.

        Returns:
            The timescale string (e.g., "1ns") if parsing is successful; otherwise None.
        """
        # Precompile regex for vector (multi-bit) changes.
        b_vector_re = re.compile(r"b([01xz]+)\s+(\S+)")
        # Translation table to replace unknown bits ('x' or 'X') with '0'
        norm_table = str.maketrans("xX", "00")

        current_scope = []
        current_time = 0
        in_header = True

        # Cache local variables to speed up inner-loop lookups.
        signals = self.signals
        hierarchy = self.hierarchy
        assume_sorted = self.assume_sorted

        try:
            if self.full_memory:
                # Read the entire file into memory
                with open(self.filename, "rb") as f:
                    content = f.read().decode("utf-8", errors="ignore")
                lines = content.splitlines()
            else:
                # Use mmap as a fallback (still split the entire content)
                import mmap
                with open(self.filename, "rb") as f:
                    with mmap.mmap(f.fileno(), 0, access=mmap.ACCESS_READ) as mm:
                        content = mm.read().decode("utf-8", errors="ignore")
                        lines = content.splitlines()

            n_lines = len(lines)
            i = 0  # Line index

            while i < n_lines:
                line = lines[i].strip()
                i += 1
                if not line:
                    continue

                # Process header until "$enddefinitions" is encountered.
                if in_header:
                    if line[0] == '$':
                        tokens = line.split()
                        directive = tokens[0]
                        if directive == "$timescale":
                            # Collect tokens until "$end" is reached.
                            timescale_tokens = tokens[1:]
                            while "$end" not in line and i < n_lines:
                                line = lines[i].strip()
                                i += 1
                                if "$end" in line:
                                    # Append tokens preceding "$end"
                                    for token in line.split():
                                        if token == "$end":
                                            break
                                        timescale_tokens.append(token)
                                    break
                                else:
                                    timescale_tokens.extend(line.split())
                            self.timescale = timescale_tokens[0] if timescale_tokens else "unknown"

                        elif directive == "$date":
                            date_info = []
                            while "$end" not in line and i < n_lines:
                                line = lines[i].strip()
                                i += 1
                                if "$end" in line:
                                    break
                                date_info.append(line)
                            self.metadata["date"] = ' '.join(date_info)

                        elif directive == "$version":
                            version_info = []
                            while "$end" not in line and i < n_lines:
                                line = lines[i].strip()
                                i += 1
                                if "$end" in line:
                                    break
                                version_info.append(line)
                            self.metadata["version"] = ' '.join(version_info)

                        elif directive == "$scope":
                            if len(tokens) >= 3:
                                current_scope.append(tokens[2])

                        elif directive == "$upscope":
                            if current_scope:
                                current_scope.pop()

                        elif directive == "$var":
                            # Format: "$var <type> <width> <id> <name> $end"
                            if len(tokens) >= 6:
                                var_id = tokens[3]
                                try:
                                    end_index = tokens.index("$end")
                                except ValueError:
                                    end_index = len(tokens)
                                var_name = ' '.join(tokens[4:end_index])
                                try:
                                    width = int(tokens[2])
                                except ValueError:
                                    width = 1

                                # Build full hierarchical name.
                                if current_scope and '.' in var_name:
                                    new_fullname = current_scope[0] + '.' + var_name
                                elif current_scope:
                                    new_fullname = '.'.join(current_scope + [var_name])
                                else:
                                    new_fullname = var_name

                                if var_id in signals:
                                    existing_signal = signals[var_id]
                                    if new_fullname not in existing_signal.aliases:
                                        existing_signal.aliases.append(new_fullname)
                                    self._insert_into_hierarchy(new_fullname, existing_signal)
                                else:
                                    signal = VCDSignal(var_id, var_name, current_scope, width)
                                    signal.fullname = new_fullname
                                    signals[var_id] = signal
                                    self._insert_into_hierarchy(signal.fullname, signal)

                        elif directive == "$enddefinitions":
                            in_header = False

                    # If the line does not start with '$' in the header, skip it.
                    continue

                # Process simulation data (after header).
                c = line[0]
                if c == '#':
                    try:
                        current_time = int(line[1:])
                    except ValueError:
                        current_time = 0
                elif c == 'b':
                    m = b_vector_re.match(line)
                    if m:
                        value, sig_id = m.groups()
                        # Replace any unknown bits with '0'
                        value = value.translate(norm_table)
                        if sig_id in signals:
                            signals[sig_id].transitions.append((current_time, value))
                else:
                    # Single-bit change: first char is value, rest is signal id.
                    value = c
                    sig_id = line[1:]
                    if value in 'xX':
                        value = '0'
                    if sig_id in signals:
                        signals[sig_id].transitions.append((current_time, value))

        except FileNotFoundError:
            print(f"VCD file not found: {self.filename}. Running without signals.")
            self.hierarchy = {}
            return None
        except Exception as e:
            print("Error while parsing:", e)
            return None

        # If file ordering isn’t guaranteed, sort each signal's transitions.
        if not assume_sorted:
            for sig in signals.values():
                sig.transitions.sort(key=lambda t: t[0])

        return self.timescale

    def _insert_into_hierarchy(self, fullname, signal):
        """
        Insert the signal into the hierarchical design structure.
        """
        # Decide how to split the fullname: if the signal name itself contains a dot
        # and scopes exist, use a two-part split; otherwise split by dot.
        if signal.hierarchy and '.' in signal.name:
            parts = [signal.hierarchy[0], signal.name]
        else:
            parts = fullname.split(".")
        subtree = self.hierarchy
        for part in parts:
            if part not in subtree:
                subtree[part] = {}
            subtree = subtree[part]
        subtree["_signal"] = signal


def convert_vector(value, width, mode):
    """
    Convert a binary string value into a formatted representation.

    Modes:
      - "hex": hexadecimal (e.g., "0xA3")
      - "bin": binary (e.g., "0b1010")
      - "decimal": decimal string

    Returns:
      Formatted string representation.
    """
    if set(value) <= {'0', '1'}:
        if mode == "hex":
            digits = ceil(width / 4)
            return f"0x{int(value, 2):0{digits}X}"
        elif mode == "bin":
            return "0b" + value
        elif mode == "decimal":
            return str(int(value, 2))
    return value.upper()


def numeric_value(v):
    """
    Convert a string representation of a signal value to its numeric equivalent.
    """
    try:
        if set(v) <= {'0', '1'}:
            return int(v, 2)
        elif v.startswith("0x"):
            return int(v, 16)
        else:
            return float(v)
    except (ValueError, TypeError):
        return 0.0


def dump_signals(signals, timescale, dump_filename="signal_dump.vcd"):
    """
    Dump the transition data of the provided signals to a VCD file.

    Parameters:
        signals (list): List of signal objects.
        timescale (str): Timescale (e.g., "1ns").
        dump_filename (str): Name of the output VCD file.
    """
    if not signals:
        return

    global_start = None
    global_end = None
    for sig in signals:
        if sig.transitions:
            first = sig.transitions[0][0]
            last = sig.transitions[-1][0]
        else:
            first = last = 0
        if global_start is None or first < global_start:
            global_start = first
        if global_end is None or last > global_end:
            global_end = last
    if global_start is None:
        global_start = 0
    if global_end is None:
        global_end = 0

    time_points = {global_start}
    for sig in signals:
        for t, _ in sig.transitions:
            if global_start <= t <= global_end:
                time_points.add(t)
    time_points = sorted(time_points)

    def get_val_at(sig, ts):
        sval = None
        for time_stamp, v in sig.transitions:
            if time_stamp <= ts:
                sval = v
            else:
                break
        return sval if sval is not None else "0"

    try:
        with open(dump_filename, "w") as f:
            f.write("$date\n")
            f.write(f"    {datetime.now().ctime()}\n")
            f.write("$end\n")
            f.write("$version\n")
            f.write("    VCD dump generated by VCDViewer\n")
            f.write("$end\n")
            f.write(f"$timescale {timescale} $end\n")
            f.write("$scope module dump $end\n")
            for sig in signals:
                f.write(f"$var wire {sig.width} {sig.id} {sig.fullname} $end\n")
            f.write("$upscope $end\n")
            f.write("$enddefinitions $end\n")
            f.write("$dumpvars\n")
            last_values = {}
            for sig in signals:
                val = get_val_at(sig, global_start)
                last_values[sig.id] = val
                if sig.width == 1:
                    f.write(f"{val}{sig.id}\n")
                else:
                    f.write(f"b{val} {sig.id}\n")
            f.write("$end\n")
            for t in time_points:
                if t == global_start:
                    continue
                changes = []
                for sig in signals:
                    new_val = get_val_at(sig, t)
                    if new_val != last_values.get(sig.id):
                        if sig.width == 1:
                            changes.append(f"{new_val}{sig.id}")
                        else:
                            changes.append(f"b{new_val} {sig.id}")
                        last_values[sig.id] = new_val
                if changes:
                    f.write(f"#{t}\n")
                    for change in changes:
                        f.write(f"{change}\n")
        print(f"Dumped {len(signals)} signal(s) to {dump_filename}.")
    except Exception as e:
        print("Error dumping signals:", e)


# Example usage:
if __name__ == "__main__":
    # Adjust 'full_memory' based on your environment and available RAM.
    parser = VCDParser("huge_file.vcd", assume_sorted=True, full_memory=True)
    timescale = parser.parse()
    if timescale:
        # For example, dump all parsed signals.
        dump_signals(list(parser.signals.values()), timescale)
