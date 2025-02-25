import pytest
from pywellen import Waveform


def count_signals(scope, hierarchy):
    """Count the total number of signals in a scope and its subscopes recursively.

    Args:
        scope: The scope to count signals in
        hierarchy: The hierarchy object containing the scope

    Returns:
        int: Total number of signals in the scope and its subscopes
    """
    count = sum(1 for _ in scope.vars(hierarchy))
    for subscope in scope.scopes(hierarchy):
        count += count_signals(subscope, hierarchy)
    return count


def print_scope(scope, hierarchy, prefix=""):
    """Print the scope hierarchy recursively.

    Args:
        scope: The scope to print
        hierarchy: The hierarchy object containing the scope
        prefix: Indentation prefix for nested scopes
    """
    scope_name = scope.full_name(hierarchy)
    if scope_name:
        print(f"{prefix}{scope_name}")
    for var in scope.vars(hierarchy):
        print(f"{prefix}  {var.full_name(hierarchy)}")
    for subscope in scope.scopes(hierarchy):
        print_scope(subscope, hierarchy, prefix + "  ")


def get_vcd_signal_count(vcd_file):
    """Get the total number of signals in a VCD file.

    Args:
        vcd_file: Path to the VCD file

    Returns:
        int: Total number of signals in the VCD file
    """
    waveform = Waveform(vcd_file)
    hierarchy = waveform.hierarchy
    total_count = 0
    for scope in hierarchy.top_scopes():
        total_count += count_signals(scope, hierarchy)
    return total_count


def print_vcd_hierarchy(vcd_file):
    """Helper function to print VCD hierarchy.

    Args:
        vcd_file: Path to the VCD file
    """
    waveform = Waveform(vcd_file)
    hierarchy = waveform.hierarchy
    print(f"\n{vcd_file} VCD Hierarchy:")
    for scope in hierarchy.top_scopes():
        print_scope(scope, hierarchy)


# Golden values for signal counts in test VCD files
VCD_SIGNAL_COUNTS = {
    "jtag.vcd": 102,
    "swerv1.vcd": 30659
}


@pytest.mark.parametrize("vcd_file", [
    "jtag.vcd",
    "swerv1.vcd"
])
def test_vcd_hierarchy(vcd_file):
    """Test reading and printing hierarchy of VCD files and verify signal counts"""
    signal_count = get_vcd_signal_count(vcd_file)
    print_vcd_hierarchy(vcd_file)
    assert signal_count == VCD_SIGNAL_COUNTS[vcd_file], \
        f"Signal count mismatch in {vcd_file}. Expected: {VCD_SIGNAL_COUNTS[vcd_file]}, Got: {signal_count}"


def test_jtag_vcd_signals():
    """Test reading signal values from jtag.vcd"""
    waveform = Waveform("jtag.vcd")

    # Get signals using get_signal_from_path
    tck_signal = waveform.get_signal_from_path("tb.tck")
    seed_signal = waveform.get_signal_from_path("tb.seed")

    assert tck_signal is not None, "tb.tck signal not found in VCD file"
    assert seed_signal is not None, "tb.seed signal not found in VCD file"

    # Test tb.tck transitions
    tck_golden = {
        0: 1,
        5: 0,
        10: 1,
        15: 0,
        20: 1,
        25: 0
    }

    # Test tb.seed transitions (in decimal format)
    seed_golden = {
        0: 12,  # b1100
        10: 828829,  # b11001010010110011101
        20: 1411815354  # b1010100001001101001011110111010
    }

    # Verify tck transitions
    for timestamp, expected_value in tck_golden.items():
        actual_value = int(tck_signal.value_at_time(timestamp))
        assert actual_value == expected_value, \
            f"tb.tck mismatch at time {timestamp}. Expected: {expected_value}, Got: {actual_value}"

    # Verify seed transitions
    for timestamp, expected_value in seed_golden.items():
        actual_value = seed_signal.value_at_time(timestamp)
        assert actual_value == expected_value, \
            f"tb.seed mismatch at time {timestamp}. Expected: {expected_value}, Got: {actual_value}"
