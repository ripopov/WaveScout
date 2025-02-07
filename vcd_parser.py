# ---------------------------
# VCD Data Classes and Parser
# ---------------------------

import re
from math import ceil


class VCDSignal:
    def __init__(self, identifier, name, hierarchy, width=1):
        self.id = identifier               # VCD signal identifier (e.g. "!")
        self.name = name                   # The declared signal name (e.g. "BinCount" or "ext.COPY_ENGINE_READ_REQUEST")
        self.hierarchy = hierarchy[:]      # List of scopes leading to the signal
        self.fullname = '.'.join(hierarchy + [name])
        self.width = width                 # Bit width of the signal
        self.transitions = []              # List of (time, value) tuples
        self.aliases = [self.fullname]     # List of full names (aliases)
        # Custom attributes:
        self.height_factor = 1             # Per-signal height factor (1 = normal, 2 = twice, etc.)
        self.rep_mode = "hex"              # Representation mode used for value pane: "hex", "bin", "decimal"
        # New toggle for wave pane drawing: if True, draw using Analog Step method.
        self.analog_render = False

class VCDParser:
    def __init__(self, filename):
        self.filename = filename
        self.signals = {}      # Mapping from var-id to VCDSignal
        self.hierarchy = {}    # Nested dictionary for design explorer
        self.timescale = None
        self.metadata = {}     # Optionally store $date, $version, etc.

    def parse(self):
        # Helper to normalize dumped values: replace any 'x' or 'X' with '0'.
        def normalize_value(val):
            return ''.join('0' if c in 'xX' else c for c in val)

        try:
            with open(self.filename, "r") as f:
                current_scope = []
                in_header = True
                current_time = 0
                for line in f:
                    line = line.strip()
                    if not line:
                        continue
                    if in_header:
                        if line.startswith("$timescale"):
                            tokens = []
                            parts = line.split()
                            if len(parts) > 1:
                                tokens.extend(parts[1:])
                            while "$end" not in line:
                                line = f.readline().strip()
                                if "$end" in line:
                                    break
                                tokens.extend(line.split())
                            self.timescale = tokens[0] if tokens else "unknown"
                        elif line.startswith("$date"):
                            date_info = []
                            while "$end" not in line:
                                line = f.readline().strip()
                                if "$end" in line:
                                    break
                                date_info.append(line)
                            self.metadata["date"] = ' '.join(date_info)
                        elif line.startswith("$version"):
                            version_info = []
                            while "$end" not in line:
                                line = f.readline().strip()
                                if "$end" in line:
                                    break
                                version_info.append(line)
                            self.metadata["version"] = ' '.join(version_info)
                        elif line.startswith("$scope"):
                            parts = line.split()
                            if len(parts) >= 3:
                                current_scope.append(parts[2])
                        elif line.startswith("$upscope"):
                            if current_scope:
                                current_scope.pop()
                        elif line.startswith("$var"):
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
                                # --- If the variable name contains a dot and there is a scope,
                                #     use only the top-level scope and leave the var_name intact.
                                if current_scope and '.' in var_name:
                                    new_fullname = current_scope[0] + '.' + var_name
                                elif current_scope:
                                    new_fullname = '.'.join(current_scope + [var_name])
                                else:
                                    new_fullname = var_name
                                # Create or update the signal.
                                if var_id in self.signals:
                                    existing_signal = self.signals[var_id]
                                    if new_fullname not in existing_signal.aliases:
                                        existing_signal.aliases.append(new_fullname)
                                    self._insert_into_hierarchy(new_fullname, existing_signal)
                                else:
                                    signal = VCDSignal(var_id, var_name, current_scope, width)
                                    # Overwrite fullname if modified.
                                    signal.fullname = new_fullname
                                    self.signals[var_id] = signal
                                    self._insert_into_hierarchy(signal.fullname, signal)
                        elif line.startswith("$enddefinitions"):
                            in_header = False
                    else:
                        if line.startswith("#"):
                            try:
                                current_time = int(line[1:])
                            except ValueError:
                                current_time = 0
                        else:
                            if line.startswith("b"):
                                m = re.match(r"b([01xz]+)\s+(\S+)", line)
                                if m:
                                    value, sig_id = m.groups()
                                    # Normalize the value (replace any x/X with 0)
                                    value = normalize_value(value)
                                    if sig_id in self.signals:
                                        self.signals[sig_id].transitions.append((current_time, value))
                            else:
                                sig_id = line[1:]
                                value = line[0]
                                # Normalize the single-character value.
                                value = '0' if value in 'xX' else value
                                if sig_id in self.signals:
                                    self.signals[sig_id].transitions.append((current_time, value))
            for sig in self.signals.values():
                sig.transitions.sort(key=lambda t: t[0])
            return self.timescale
        except FileNotFoundError:
            print(f"VCD file not found: {self.filename}. Running without loading any signals.")
            self.hierarchy = {}
            return None

    def _insert_into_hierarchy(self, fullname, signal):
        # If the signal's declared name contains a dot (and there is a scope),
        # then do not split the var_name further.
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
    """Convert a binary string value into a string using the given mode.
       For value display, mode is one of 'hex', 'bin', or 'decimal'."""
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
    try:
        if set(v) <= {'0', '1'}:
            return int(v, 2)
        elif v.startswith("0x"):
            return int(v, 16)
        else:
            return float(v)
    except (ValueError, TypeError):
        return 0.0
