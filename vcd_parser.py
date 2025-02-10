# vcd_parser.py
# VCD Data Classes and Parser
# This module provides classes and functions to parse VCD (Value Change Dump) files.
# VCD files are used in digital design simulations to record changes in signal values over time.

import re
from math import ceil
from datetime import datetime


class VCDSignal:
    """
    Class representing a single signal extracted from a VCD file.
    Stores metadata about the signal (such as its name, hierarchy, width)
    as well as the time-stamped value transitions.
    """

    def __init__(self, identifier, name, hierarchy, width=1):
        self.id = identifier  # Unique VCD identifier for the signal (e.g., "!")
        self.name = name  # Declared name of the signal (e.g., "BinCount" or "ext.COPY_ENGINE_READ_REQUEST")
        self.hierarchy = hierarchy[:]  # List of hierarchical scopes leading to the signal (copied to avoid external modification)
        self.fullname = '.'.join(hierarchy + [name])  # Full hierarchical name (e.g., "top.sub.BinCount")
        self.width = width  # Bit width of the signal (default is 1 for single-bit signals)
        self.transitions = []  # List of (time, value) tuples recording when the signal changes value
        self.aliases = [self.fullname]  # List of alternative full names (aliases) for the signal

        # Additional custom attributes for display and rendering in waveform viewers:
        self.height_factor = 1  # Vertical scaling factor for waveform display (1 = normal, 2 = double height, etc.)
        self.rep_mode = "hex"  # Default representation mode for displaying the signal value; options: "hex", "bin", or "decimal"
        self.analog_render = False  # Toggle to enable analog (step) style rendering in waveform displays


class VCDParser:
    """
    Class responsible for parsing a VCD file and extracting signals and their transitions.
    Also builds a hierarchical representation of the design for easier exploration.
    """

    def __init__(self, filename):
        self.filename = filename
        self.signals = {}  # Dictionary mapping VCD variable IDs to VCDSignal objects
        self.hierarchy = {}  # Nested dictionary representing the design's hierarchical structure
        self.timescale = None  # Timescale of the simulation (e.g., "1ns", "10ps") as defined in the VCD header
        self.metadata = {}  # Dictionary for storing additional VCD metadata (e.g., date, version)

    def parse(self):
        """
        Parse the VCD file specified by self.filename.

        The parser reads the header to extract metadata, scope, and variable definitions,
        then processes the rest of the file to record value transitions for each signal.

        Returns:
            The timescale as specified in the VCD file, or None if the file is not found.
        """

        # Helper function to normalize signal values by replacing unknown bits ('x' or 'X') with '0'
        def normalize_value(val):
            return ''.join('0' if c in 'xX' else c for c in val)

        try:
            with open(self.filename, "r") as f:
                current_scope = []  # List to keep track of the current scope hierarchy during parsing
                in_header = True  # Flag indicating whether we are still reading the header section
                current_time = 0  # Variable to track the current simulation time
                for line in f:
                    line = line.strip()
                    if not line:
                        continue  # Skip empty lines

                    if in_header:
                        # Process header directives and metadata.
                        if line.startswith("$timescale"):
                            # Extract the simulation timescale (e.g., "1ns", "10ps")
                            tokens = []
                            parts = line.split()
                            if len(parts) > 1:
                                tokens.extend(parts[1:])
                            # Read additional lines until the end of the timescale block is reached
                            while "$end" not in line:
                                line = f.readline().strip()
                                if "$end" in line:
                                    break
                                tokens.extend(line.split())
                            # Set the timescale to the first token found, or "unknown" if none found
                            self.timescale = tokens[0] if tokens else "unknown"

                        elif line.startswith("$date"):
                            # Extract the date metadata from the VCD header
                            date_info = []
                            while "$end" not in line:
                                line = f.readline().strip()
                                if "$end" in line:
                                    break
                                date_info.append(line)
                            self.metadata["date"] = ' '.join(date_info)

                        elif line.startswith("$version"):
                            # Extract version information from the VCD header
                            version_info = []
                            while "$end" not in line:
                                line = f.readline().strip()
                                if "$end" in line:
                                    break
                                version_info.append(line)
                            self.metadata["version"] = ' '.join(version_info)

                        elif line.startswith("$scope"):
                            # When a new scope is declared, add its name to the current scope list.
                            parts = line.split()
                            if len(parts) >= 3:
                                current_scope.append(parts[2])

                        elif line.startswith("$upscope"):
                            # End the current scope by removing the last scope from the list.
                            if current_scope:
                                current_scope.pop()

                        elif line.startswith("$var"):
                            # Parse a variable definition line that declares a signal.
                            # Format: $var <type> <width> <id> <name> $end
                            parts = line.split()
                            if len(parts) >= 6:
                                var_id = parts[3]
                                try:
                                    end_index = parts.index("$end")
                                except ValueError:
                                    end_index = len(parts)
                                var_name = ' '.join(parts[4:end_index])
                                try:
                                    width = int(parts[2])
                                except ValueError:
                                    width = 1

                                # Determine the full hierarchical name of the signal.
                                # If the signal name contains a dot and scopes exist, combine only the top-level scope with the var_name.
                                if current_scope and '.' in var_name:
                                    new_fullname = current_scope[0] + '.' + var_name
                                elif current_scope:
                                    new_fullname = '.'.join(current_scope + [var_name])
                                else:
                                    new_fullname = var_name

                                # If the signal already exists, update its alias list and hierarchy.
                                if var_id in self.signals:
                                    existing_signal = self.signals[var_id]
                                    if new_fullname not in existing_signal.aliases:
                                        existing_signal.aliases.append(new_fullname)
                                    self._insert_into_hierarchy(new_fullname, existing_signal)
                                else:
                                    # Create a new VCDSignal object for this signal.
                                    signal = VCDSignal(var_id, var_name, current_scope, width)
                                    # Overwrite the default fullname if modified by the current scope rules.
                                    signal.fullname = new_fullname
                                    self.signals[var_id] = signal
                                    self._insert_into_hierarchy(signal.fullname, signal)

                        elif line.startswith("$enddefinitions"):
                            # End of header section; subsequent lines contain simulation data.
                            in_header = False

                    else:
                        # Process simulation data (value changes and time markers).
                        if line.startswith("#"):
                            # A line starting with '#' indicates a new simulation time.
                            try:
                                current_time = int(line[1:])
                            except ValueError:
                                current_time = 0
                        else:
                            # Process value change entries.
                            if line.startswith("b"):
                                # A vector (multi-bit) value change is indicated by a leading 'b'.
                                # Expected format: b<binary_value> <signal_id>
                                m = re.match(r"b([01xz]+)\s+(\S+)", line)
                                if m:
                                    value, sig_id = m.groups()
                                    # Normalize the value by converting any unknown bits ('x' or 'X') to '0'
                                    value = normalize_value(value)
                                    if sig_id in self.signals:
                                        self.signals[sig_id].transitions.append((current_time, value))
                            else:
                                # A single-bit value change is indicated by a line starting with the value.
                                # Format: <value><signal_id>
                                sig_id = line[1:]
                                value = line[0]
                                # Normalize single-bit value (convert 'x' or 'X' to '0')
                                value = '0' if value in 'xX' else value
                                if sig_id in self.signals:
                                    self.signals[sig_id].transitions.append((current_time, value))
            # After processing the file, sort each signal's transitions by time.
            for sig in self.signals.values():
                sig.transitions.sort(key=lambda t: t[0])
            return self.timescale

        except FileNotFoundError:
            # If the specified VCD file does not exist, notify the user and continue without signals.
            print(f"VCD file not found: {self.filename}. Running without loading any signals.")
            self.hierarchy = {}
            return None

    def _insert_into_hierarchy(self, fullname, signal):
        """
        Insert the signal into the hierarchical design structure (self.hierarchy).

        The hierarchy is built as a nested dictionary where each key represents a scope or signal name.
        If the signal's declared name contains a dot and a scope is defined, the var_name is kept intact
        under the top-level scope; otherwise, the fullname is split at the dots.

        Parameters:
            fullname (str): The full hierarchical name of the signal.
            signal (VCDSignal): The signal object to be inserted into the hierarchy.
        """
        # Decide how to split the fullname into parts for the hierarchy.
        if signal.hierarchy and '.' in signal.name:
            # If the signal name already contains a dot and scopes exist, only the top-level scope is used.
            parts = [signal.hierarchy[0], signal.name]
        else:
            parts = fullname.split(".")
        subtree = self.hierarchy
        for part in parts:
            if part not in subtree:
                subtree[part] = {}
            subtree = subtree[part]
        # Store a reference to the signal at the leaf of the hierarchy.
        subtree["_signal"] = signal


def convert_vector(value, width, mode):
    """
    Convert a binary string value into a formatted string representation.

    This function interprets a string containing a binary number and returns it
    formatted in the specified mode: hexadecimal ('hex'), binary ('bin'), or decimal ('decimal').

    Parameters:
        value (str): The binary string (e.g., "1010") to convert.
        width (int): The bit width of the signal; used to determine the number of hex digits.
        mode (str): The desired display mode. Should be one of 'hex', 'bin', or 'decimal'.

    Returns:
        str: The formatted string representation of the value.
    """
    if set(value) <= {'0', '1'}:
        if mode == "hex":
            # Calculate the number of hexadecimal digits needed (4 bits per hex digit)
            digits = ceil(width / 4)
            return f"0x{int(value, 2):0{digits}X}"
        elif mode == "bin":
            return "0b" + value
        elif mode == "decimal":
            return str(int(value, 2))
    # If the value contains non-binary characters, return it in uppercase.
    return value.upper()


def numeric_value(v):
    """
    Convert a string representation of a signal value to its numeric equivalent.

    The function attempts to interpret the input as a binary number, hexadecimal (if it starts with '0x'),
    or a floating-point number. If conversion fails, it returns 0.0.

    Parameters:
        v (str): The signal value as a string.

    Returns:
        int or float: The numeric value of the signal.
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
        signals (list): List of signal objects. Each must have:
                        - transitions (list of (time, value) tuples)
                        - width (int)
                        - id (str)
                        - fullname (str)
        timescale (str): Timescale string (e.g., "1ns") to be written in the VCD file.
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
            first = 0
            last = 0
        if global_start is None or first < global_start:
            global_start = first
        if global_end is None or last > global_end:
            global_end = last
    if global_start is None:
        global_start = 0
    if global_end is None:
        global_end = 0

    time_points = set()
    for sig in signals:
        for t, _ in sig.transitions:
            if global_start <= t <= global_end:
                time_points.add(t)
    time_points.add(global_start)
    time_points = sorted(time_points)

    def get_val_at(sig, ts):
        sval = None
        for time_stamp, v in sig.transitions:
            if time_stamp <= ts:
                sval = v
            else:
                break
        if sval is None:
            sval = "0"
        return sval

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
