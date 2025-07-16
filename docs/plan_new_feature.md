# WaveScout Feature Planning Guide

## Context
WaveScout is a Digital/Mixed signal waveform viewer similar to GtkWave, Verdi, ModelSim Waveform Viewer, etc. It uses a Model-View architecture with Qt6/PySide6 for UI and a Rust backend (pywellen) for waveform data processing.

## Your Task
When a user provides a new feature or bugfix description, create a comprehensive technical plan following this guide.

## Step-by-Step Planning Process

### 1. Requirements Analysis
- Extract and preserve ALL specific details from the user's prompt verbatim
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
- Backward compatibility strategy

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
If the feature involves complex logic:
1. Break down into numbered steps
2. Specify input/output data types
3. Note performance considerations
4. Identify caching opportunities

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

### 6. Testing Strategy
Include a testing approach:
- Unit tests for pure logic
- Integration tests with sample waveforms
- UI interaction tests with pytest-qt
- Performance benchmarks if applicable

### 7. Performance Considerations
Address these aspects:
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

## Document Structure Template

```markdown
# Feature: [Feature Name]

## Introduction
[2-3 sentences setting context and describing the feature's purpose]

## Requirements
[Verbatim list of user requirements, preserving all specific details]

## Data Model Changes
### Modified Classes
- `ClassName`: [specific fields/enums to add with types and defaults]

### New Classes/Enums
[If applicable]

## Implementation

### 1. [Component Name] Changes
**File**: `path/to/file.py`
**Functions**: `function_name()`, `class_name.method()`
**Changes**:
- [Specific change description]
- [Integration with other components]

### 2. [Next Component]...

## Algorithms
[Step-by-step descriptions if complex logic is involved]

## UI Integration
[How users will access/use the feature]

## Testing Approach
[Specific test scenarios]

## Performance Impact
[Analysis of performance implications]

## [Optional] Implementation Phases
[Only if genuinely needed for complex features]
```

## Quality Checklist
Before finalizing the plan, ensure:
- [ ] All user requirements are addressed verbatim
- [ ] Data model changes are fully specified with types and defaults
- [ ] All affected files and functions are identified by exact name
- [ ] Algorithms are described step-by-step
- [ ] UI integration points are clear
- [ ] Testing strategy is defined
- [ ] Performance implications are considered
- [ ] The plan is concise but complete

## Output
Write the plan to: `docs/features/<N>_<BRIEF>_plan.md`
- `<N>`: Next available 4-digit number (0001, 0002, etc.)
- `<BRIEF>`: 1-2 word feature description (snake_case)