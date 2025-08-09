# WaveScout Feature Planning Guide

## Context
WaveScout is a Digital/Mixed signal waveform viewer similar to GtkWave, Verdi, ModelSim Waveform Viewer, etc. It uses a Model-View architecture with Qt6/PySide6 for UI and a Rust backend (pywellen) for waveform data processing.

## Your Task
When a user provides a new feature or bugfix description, create a comprehensive technical plan following this guide.

## Step-by-Step Planning Process

### 1. Requirements Analysis
- Extract and preserve ALL specific details from the user's prompt
- Identify the core functionality being requested
- Note any performance, UI/UX, or compatibility requirements mentioned
- If requirements are unclear, ask up to 5 clarifying questions before proceeding

### 2. Codebase Research
Research the following areas based on feature requirements:

#### Essential Files to Examine:
- **`wavescout/data_model.py`**: Core data structures (ALWAYS analyze this first)
- **`wavescout/waveform_canvas.py`**: If feature affects rendering
- **`wavescout/signal_names_view.py`**: If feature needs UI controls/menus
- **`wavescout/signal_sampling.py`**: If feature affects data processing
- **`wavescout/signal_renderer.py`**: If feature changes visual representation
- **`wavescout/waveform_controller.py`**: If feature affects coordination logic
- **`wavescout/waveform_item_model.py`**: If feature affects Qt model/view

#### Architecture Patterns to Consider:
- Normalized viewport system (0.0-1.0 coordinates)
- Caching strategies (TransitionCache, SignalRangeCache)
- Command pattern for undo/redo
- Signal/slot communication between components

### 3. Data Model Design
The data model (`data_model.py`) is the single source of truth. Plan changes carefully:

#### Required Specifications:
- New fields for existing dataclasses (with types and defaults)
- New enums for modes/states
- New dataclasses if needed
- Persistence implications (YAML serialization)

#### Example Data Model Addition:
```python
@dataclass
class DisplayFormat:
    # Existing fields...
    new_feature_mode: NewFeatureEnum = NewFeatureEnum.DEFAULT  # Add with default
```

### 4. Implementation Planning

#### File-by-File Changes:
For each file that needs modification, specify:
- **File Path**: Full path from project root
- **Functions/Classes to Modify**: Exact names
- **Nature of Changes**: What needs to be added/modified (NOT the actual code)
- **Integration Points**: How it connects with other components

#### Algorithm Descriptions:
If the feature involves complex logic: Write informal algorithm descriptions step-by-step.

### 5. UI Integration
If the feature has UI components:

#### Context Menu Integration:
- Location in `SignalNamesView._show_context_menu()`
- Menu structure and grouping
- Signal connections to actions

#### Visual Updates:
- Rendering changes in `WaveformCanvas.paintEvent()`
- Custom delegates if needed
- Synchronization across panels

### 7. Performance Considerations
Address these aspects if changes are expected to have a significant impact on performance (for example reading all signal values, or multiple signals at once):
- Cache invalidation triggers
- Rendering optimization needs
- Memory usage implications
- Large file handling

### 8. Phase Planning (Only for Complex Features)
Break into phases ONLY if the feature is genuinely complex:
- **Phase 1**: Core functionality
- **Phase 2**: UI integration
- **Phase 3**: Optimizations
Each phase should be independently testable and deployable.

## Output
Write the plan to: `docs/features/<N>_<BRIEF>_plan.md`
- `<N>`: Next available 4-digit number (0001, 0002, etc.)
- `<BRIEF>`: 1-2 word feature description (snake_case)