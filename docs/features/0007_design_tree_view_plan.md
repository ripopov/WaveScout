# DesignTreeView Feature Plan

## Requirements Summary

Create a redesigned design tree panel as a standalone widget called `DesignTreeView` with two viewing modes:

1. **Unified Mode**: Current implementation showing scopes and variables in a single tree (with optimization to expand only first scope on load)
2. **Split Mode**: Two-panel view with scopes tree on top and filtered variable list on bottom

Mode preference persisted in QSettings, with a toggle button in the header to switch between modes.

## 1. Requirements Analysis

### Core Requirements
- Standalone widget class `DesignTreeView` encapsulating all design tree functionality
- Two distinct viewing modes: Unified and Split
- Mode toggle button in widget header
- Persistence of selected mode in QSettings
- Split mode features:
  - Top panel: QTreeView showing only scopes (single selection)
  - Bottom panel: VarsView showing variables with Name, Type, Bit Range columns
  - Multi-selection support in VarsView
  - Fuzzy filtering text input for VarsView
  - Same keyboard shortcuts ('i'/'I') for adding signals
- Unified mode optimization: Expand only first scope on initial load

### Preserved Functionality
- All existing selection modes and shortcuts
- Signal addition workflow (double-click and 'I' shortcut)
- Progress dialogs for batch operations
- Status bar updates

## 2. Codebase Research Summary

### Current Implementation
- **Design tree model**: `wavescout/design_tree_model.py` - Core tree model with DesignTreeNode and DesignTreeModel classes
- **Integration**: `scout.py` lines 66-81, 199-223, 301-426 - Design tree setup and signal handling
- **QSettings usage**: Already established pattern with `QSettings("WaveScout", "Demo")`
- **No existing filtering**: Will need to implement fuzzy filtering from scratch

### Key Classes to Refactor
- `DesignTreeNode`: Already suitable for both modes
- `DesignTreeModel`: Can be reused for Unified mode and scope-only tree
- Signal addition logic: Extract from `scout.py` into new widget

## 3. Data Model Design

### New Enums
```python
# In wavescout/data_model.py or new file wavescout/design_tree_view.py
from enum import Enum

class DesignTreeViewMode(Enum):
    UNIFIED = "unified"
    SPLIT = "split"
```

### Settings Keys
- `"design_tree_view_mode"`: Stores the selected mode (default: "unified")

## 4. Implementation Planning

### New Files to Create

#### `/home/ripopov/PycharmProjects/WaveScout/wavescout/design_tree_view.py`
**Main widget class containing:**
- `DesignTreeView(QWidget)`: Main container widget
- Mode management and persistence
- Header with mode toggle button
- Stacked widget or dynamic layout for mode switching
- Signal handling methods extracted from scout.py

#### `/home/ripopov/PycharmProjects/WaveScout/wavescout/scope_tree_model.py`
**Scope-only tree model for split mode:**
- `ScopeTreeModel(QAbstractItemModel)`: Filters out variables, shows only scopes
- Single selection mode enforcement
- Signal emission when scope selection changes

#### `/home/ripopov/PycharmProjects/WaveScout/wavescout/vars_view.py`
**Variable list view for split mode:**
- `VarsView(QWidget)`: Contains QTableView and filter input
- `VarsModel(QAbstractTableModel)`: Three-column model (Name, Type, Bit Range)
- `FuzzyFilterProxyModel(QSortFilterProxyModel)`: Implements fuzzy filtering
- Multi-selection support
- Keyboard shortcut handling

### Files to Modify

#### `/home/ripopov/PycharmProjects/WaveScout/scout.py`
**Changes:**
- Replace current design tree setup (lines 66-81) with `DesignTreeView` instantiation
- Move signal handling methods to `DesignTreeView`:
  - `_on_design_tree_double_click`
  - `_get_full_signal_path`
  - `_find_signal_handle`
  - `_add_signals_from_design_tree`
  - Related eventFilter logic for 'I' shortcut
- Update hierarchy loading to call method on new widget

#### `/home/ripopov/PycharmProjects/WaveScout/wavescout/design_tree_model.py`
**Changes:**
- Add method to get all variables for a given scope path
- Add method to expand only first scope (optimization)
- Ensure model can work with both unified and scope-only views

## 5. Component Architecture

### DesignTreeView Widget Structure
```
DesignTreeView (QWidget)
├── Header (QWidget)
│   ├── Title Label
│   └── Mode Toggle Button (QPushButton or QToolButton)
├── Content Area (QStackedWidget or dynamic)
│   ├── Unified Mode
│   │   └── QTreeView with DesignTreeModel
│   └── Split Mode
│       ├── QSplitter (vertical)
│       │   ├── Scope Tree (QTreeView with ScopeTreeModel)
│       │   └── VarsView (custom widget)
│       │       ├── Filter Input (QLineEdit)
│       │       └── Variables Table (QTableView with VarsModel + FuzzyFilterProxyModel)
```

### Signal Flow in Split Mode
1. User selects scope in top panel
2. ScopeTreeModel emits scope_changed signal with scope path
3. VarsView updates VarsModel with variables from selected scope
4. User types in filter input
5. FuzzyFilterProxyModel updates visible variables
6. User selects variables and presses 'I'
7. Selected variables added to waveform session

## 6. UI Integration

### Mode Toggle Button
- Location: Top-right of DesignTreeView header
- Icon-based toggle or text button ("Unified"/"Split")
- Tooltip explaining the modes
- Instant mode switch without data reload

### Unified Mode Behavior
- Preserve all current functionality
- Optimization: Expand only first scope on load
- Implementation: Call `expandToDepth(1)` instead of `expandToDepth(2)`

### Split Mode Layout
- **Scope Tree (30% height)**:
  - Shows folder icons for scopes
  - Single selection mode
  - Auto-expand to show some initial structure
  
- **VarsView (70% height)**:
  - Filter input with placeholder "Filter variables..."
  - Table headers: Name | Type | Bit Range
  - Alternating row colors
  - Multi-selection with Ctrl/Shift
  - Double-click to add single variable
  - 'I' shortcut for batch addition

### Keyboard Shortcuts
- Preserve 'i'/'I' shortcuts in both modes
- Add Ctrl+F to focus filter input in split mode
- Escape to clear filter

## 7. Fuzzy Filtering Algorithm

### Implementation Approach
Implement IDE-style fuzzy matching similar to VSCode or IntelliJ IDEA's file/variable search, which provides:
- Character-order matching with scoring based on match quality
- Preference for consecutive character matches
- Bonus points for matches at word boundaries (camelCase, snake_case)
- Highlighting of matched characters in results

### Recommended Python Library: `rapidfuzz`
**Why rapidfuzz:**
- Fast C++ implementation with Python bindings (100x faster than pure Python)
- Provides multiple fuzzy matching algorithms including partial_ratio and token_set_ratio
- Scoring system (0-100) for ranking matches
- Used in production by many Python projects
- Easy integration with Qt models via score-based sorting

**Alternative Options:**
- `fuzzywuzzy`: Original Python library, slower but simpler API
- `python-Levenshtein`: Fast but more focused on edit distance
- Custom implementation: For full control over scoring logic

### Implementation with rapidfuzz
```python
from rapidfuzz import fuzz, process

# Score-based filtering
def fuzzy_filter(query, signal_names):
    # Returns list of (signal_name, score, index) tuples
    results = process.extract(
        query, 
        signal_names,
        scorer=fuzz.WRatio,  # Weighted ratio for better results
        score_cutoff=60  # Minimum score threshold
    )
    return [name for name, score, _ in results]
```

### Scoring Examples (VSCode/IDEA-like behavior)
- Query: "clk" 
  - "clk" → 100 (exact match)
  - "clock" → 90 (consecutive match)
  - "sys_clk" → 85 (word boundary match)
  - "clk_enable" → 85 (prefix match)
  - "c_latch_k" → 65 (scattered match)

- Query: "rst"
  - "rst" → 100
  - "reset" → 90
  - "rst_n" → 95
  - "register_set" → 70
  - "r_state" → 60

- Query: "adrd" 
  - "addr_read" → 95 (boundary matches)
  - "address_read" → 90
  - "add_read" → 85
  - "addr_rd" → 95

### Match Highlighting
For visual feedback like VSCode/IDEA:
- Store match positions from fuzzy algorithm
- Use Qt's rich text or custom delegate to highlight matched characters
- Bold or different color for matched subsequence

## 8. Session State Management

### Settings Persistence
```python
# In DesignTreeView.__init__
self.settings = QSettings("WaveScout", "Demo")
saved_mode = self.settings.value("design_tree_view_mode", "unified")
self.set_mode(DesignTreeViewMode(saved_mode))

# In mode toggle handler
self.settings.setValue("design_tree_view_mode", new_mode.value)
```

### State Preservation During Mode Switch
- Remember expanded state of scopes
- Remember selected scope in split mode
- Clear filter when switching modes
- Maintain scroll position where possible

## 9. Implementation Phases

### Phase 1: Core Widget Structure
1. Create `DesignTreeView` class with basic structure
2. Extract existing design tree functionality from scout.py
3. Implement mode toggle UI without functionality
4. Ensure unified mode works identically to current implementation
5. Add first-scope-only expansion optimization

### Phase 2: Split Mode Implementation
1. Create `ScopeTreeModel` for scope-only display
2. Create `VarsView` with basic table display
3. Implement scope selection → variable display workflow
4. Add multi-selection support in VarsView
5. Connect signal addition methods

### Phase 3: Filtering and Polish
1. Add `rapidfuzz` dependency to pyproject.toml
2. Implement `FuzzyFilterProxyModel` using rapidfuzz scoring
3. Add filter input and connect to proxy model
4. Implement match highlighting in VarsView delegate
5. Add keyboard shortcuts (Ctrl+F for filter focus)
6. Add mode persistence to QSettings
7. Polish UI with proper spacing and icons

## 10. Testing Considerations

### Test Cases
1. Mode switching preserves waveform database connection
2. Signal addition works in both modes
3. Fuzzy filtering correctly matches signals
4. Settings persistence across application restarts
5. Performance with large hierarchies (10000+ signals)
6. Keyboard shortcuts work in both modes
7. Progress dialogs appear for batch operations

### Edge Cases
- Empty scope selection in split mode
- Switching modes with active filter
- Very long signal names in VarsView
- Scope with no variables
- Deep hierarchy navigation

## 11. Future Enhancements (Not in Initial Implementation)
- Regex filtering option alongside fuzzy filtering
- Column sorting in VarsView
- Drag-and-drop from both modes to waveform canvas
- Recent/favorite scopes in split mode
- Export filtered variable list