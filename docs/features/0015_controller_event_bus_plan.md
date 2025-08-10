# Feature Plan: Controller-Centric Mutations with Typed Event Bus

## Executive Summary

This plan establishes a clean architecture pattern where all domain mutations flow through a centralized controller API, with changes propagated via a typed event bus. The UI layer becomes purely reactive, eliminating direct mutations of domain objects.

**Key Benefits:**
- Single source of truth for all state mutations
- Type-safe event propagation without Qt dependencies  
- Clear separation between domain logic and UI concerns
- Easier testing and debugging with explicit event flow
- Foundation for undo/redo and collaborative features

## Requirements Analysis

### Functional Requirements

**Core Architecture:**
- All domain mutations must flow through `WaveformController` methods
- UI components (WaveScoutWidget, SignalNamesView) express intent via controller calls only
- Qt model (WaveformItemModel) receives changes via events, not direct manipulation
- Typed event bus with dataclass payloads replaces ad-hoc callbacks
- Backend boundary uses `WaveformDBProtocol` instead of `Any` typing

**Preserved Behaviors:**
- Signal/group deletion with multi-selection support
- Drag-and-drop reordering within and between groups
- Context menu actions (format changes, render type, scaling, rename)
- Viewport and cursor synchronization
- Marker management operations

### Non-Functional Requirements

**Performance:**
- Initial implementation uses model reset for correctness
- Optimization path: fine-grained Qt model updates based on event payloads
- Lazy evaluation where possible (e.g., cache invalidation markers)

**Type Safety:**
- No `Any` types per project guidelines
- Explicit `Optional`, `TypeAlias`, and `TypedDict` usage
- Protocol-based backend interface
- Generic type constraints on event bus

**Maintainability:**
- Controller methods remain UI-framework agnostic (no Qt types)
- Clear event naming and payload structure
- Comprehensive type hints for IDE support

## Architecture Analysis

### Current State Assessment

Based on codebase review:

1. **WaveformController** already exists with:
   - Basic callback mechanism (`_callbacks` dict)
   - Viewport, cursor, and marker operations
   - Selection tracking by instance IDs
   - Missing: structural mutations (delete, group, move, rename)

2. **Data Model** observations:
   - `WaveformSession.waveform_db` typed as `Optional[Any]` - needs Protocol
   - `SignalNode` has instance_id generation for unique identification
   - Tree structure with parent/child relationships
   - Display format and render configuration per node

3. **UI Layer** patterns:
   - `SignalNamesView` directly mutates node properties (format, render_type)
   - `WaveformItemModel` performs tree surgery during drag-drop
   - No centralized mutation tracking or event propagation

4. **Existing Protocol:**
   - `WaveformDBProtocol` already defined in `wavescout/protocols.py`
   - Comprehensive interface for waveform operations
   - Ready to replace `Any` typing

### Gap Analysis

**Missing Components:**
1. Typed event system to replace string-based callbacks
2. Controller methods for structural mutations
3. Event subscriptions in UI components
4. Decoupling of model updates from direct manipulation

## Data Model Design

### Type Strengthening

```python
# wavescout/data_model.py
from wavescout.protocols import WaveformDBProtocol

@dataclass
class WaveformSession:
    waveform_db: Optional[WaveformDBProtocol] = None  # Changed from Any
    # ... rest unchanged
```

### Event Type Hierarchy

```python
# wavescout/application/events.py
from dataclasses import dataclass
from typing import Literal, Optional, Dict, List, Any
from wavescout.data_model import Time, SignalNodeID

@dataclass(frozen=True)
class Event:
    """Base class for all events."""
    timestamp: float = field(default_factory=time.time)

@dataclass(frozen=True)
class StructureChangedEvent(Event):
    """Emitted when signal tree structure changes."""
    change_kind: Literal['insert', 'delete', 'move', 'group', 'ungroup']
    affected_ids: List[SignalNodeID]
    parent_id: Optional[SignalNodeID] = None
    insert_row: Optional[int] = None
    
@dataclass(frozen=True)  
class FormatChangedEvent(Event):
    """Emitted when signal display format changes."""
    node_id: SignalNodeID
    changes: Dict[str, Any]  # Will migrate to TypedDict
    
@dataclass(frozen=True)
class ViewportChangedEvent(Event):
    """Emitted when viewport bounds change."""
    old_left: float
    old_right: float
    new_left: float
    new_right: float
    
@dataclass(frozen=True)
class CursorMovedEvent(Event):
    """Emitted when cursor position changes."""
    old_time: Time
    new_time: Time

@dataclass(frozen=True)
class SelectionChangedEvent(Event):
    """Emitted when node selection changes."""
    old_selection: List[SignalNodeID]
    new_selection: List[SignalNodeID]
```

## Implementation Design

### Event Bus Architecture

```python
# wavescout/application/event_bus.py
from typing import TypeVar, Generic, Callable, Dict, List, Type
import logging

T = TypeVar('T', bound=Event)

class EventBus:
    """Type-safe publish-subscribe event bus."""
    
    def __init__(self):
        self._subscribers: Dict[Type[Event], List[Callable]] = {}
        self._logger = logging.getLogger(__name__)
    
    def subscribe(self, event_type: Type[T], handler: Callable[[T], None]) -> None:
        """Subscribe to events of specific type."""
        if event_type not in self._subscribers:
            self._subscribers[event_type] = []
        self._subscribers[event_type].append(handler)
    
    def unsubscribe(self, event_type: Type[T], handler: Callable[[T], None]) -> None:
        """Unsubscribe from events."""
        if event_type in self._subscribers:
            try:
                self._subscribers[event_type].remove(handler)
            except ValueError:
                pass
                
    def publish(self, event: Event) -> None:
        """Publish event to all subscribers."""
        event_type = type(event)
        for handler in self._subscribers.get(event_type, []):
            try:
                handler(event)
            except Exception as e:
                self._logger.error(f"Handler error for {event_type.__name__}: {e}")
                if __debug__:
                    raise
```

### Controller API Extensions

```python
# wavescout/waveform_controller.py additions

class WaveformController:
    # ... existing code ...
    
    def __init__(self):
        # ... existing init ...
        self.event_bus = EventBus()
        
    # ---- Structural Mutations ----
    
    def delete_nodes_by_ids(self, ids: Iterable[SignalNodeID]) -> None:
        """Delete nodes from the signal tree."""
        if not self.session:
            return
            
        ids_list = list(ids)
        if not ids_list:
            return
            
        # Collect nodes to delete
        nodes_to_delete = []
        for node in self._iter_all_nodes():
            if node.instance_id in ids_list:
                nodes_to_delete.append(node)
        
        # Remove from tree
        for node in nodes_to_delete:
            if node.parent:
                node.parent.children.remove(node)
            elif node in self.session.root_nodes:
                self.session.root_nodes.remove(node)
                
        # Emit event
        self.event_bus.publish(StructureChangedEvent(
            change_kind='delete',
            affected_ids=ids_list
        ))
        
    def group_nodes(
        self,
        ids: Iterable[SignalNodeID],
        group_name: str,
        mode: GroupRenderMode
    ) -> SignalNodeID:
        """Create a new group containing specified nodes."""
        if not self.session:
            return -1
            
        # Implementation details...
        # Returns new group's instance_id
        
    def move_nodes(
        self,
        node_ids: List[SignalNodeID],
        target_parent_id: Optional[SignalNodeID],
        insert_row: int
    ) -> None:
        """Move nodes to new position in tree."""
        if not self.session:
            return
            
        # Implementation details...
        
        self.event_bus.publish(StructureChangedEvent(
            change_kind='move',
            affected_ids=node_ids,
            parent_id=target_parent_id,
            insert_row=insert_row
        ))
        
    def set_node_format(self, node_id: SignalNodeID, **kwargs) -> None:
        """Update display format properties."""
        node = self._find_node_by_id(node_id)
        if not node:
            return
            
        changes = {}
        for key, value in kwargs.items():
            if hasattr(node.format, key):
                old_value = getattr(node.format, key)
                if old_value != value:
                    setattr(node.format, key, value)
                    changes[key] = value
                    
        if changes:
            self.event_bus.publish(FormatChangedEvent(
                node_id=node_id,
                changes=changes
            ))
            
    def rename_node(self, node_id: SignalNodeID, nickname: str) -> None:
        """Set user-defined nickname for node."""
        node = self._find_node_by_id(node_id)
        if not node:
            return
            
        if node.nickname != nickname:
            node.nickname = nickname
            self.event_bus.publish(FormatChangedEvent(
                node_id=node_id,
                changes={'nickname': nickname}
            ))
```

### Migration Strategy

**Phase 1: Foundation (Low Risk)**
- Update `WaveformSession.waveform_db` typing to use Protocol
- Implement event classes and EventBus
- Add to controller without removing callbacks yet

**Phase 2: Controller APIs (Medium Risk)**
- Add mutation methods to controller
- Update unit tests for new APIs
- Maintain backward compatibility

**Phase 3: UI Migration (Higher Risk)**
- Replace direct mutations with controller calls
- Subscribe to events for updates
- Initially use model reset, optimize later

**Phase 4: Optimization (Low Risk)**
- Implement fine-grained model updates
- Add caching and lazy evaluation
- Performance profiling and tuning

## Testing Strategy

### Unit Tests
```python
def test_delete_nodes_emits_event():
    controller = WaveformController()
    events = []
    controller.event_bus.subscribe(
        StructureChangedEvent,
        lambda e: events.append(e)
    )
    
    # Setup session with nodes
    session = create_test_session()
    controller.set_session(session)
    
    # Delete nodes
    controller.delete_nodes_by_ids([1, 2, 3])
    
    # Verify event
    assert len(events) == 1
    assert events[0].change_kind == 'delete'
    assert events[0].affected_ids == [1, 2, 3]
```

### Integration Tests
- Drag-drop operations through controller
- Multi-selection deletions
- Format changes with canvas updates
- Event propagation chain validation

## Performance Considerations

### Memory Impact
- Event objects: ~100 bytes per event (short-lived)
- Subscriber lists: ~8 bytes per subscription
- Total overhead: < 10KB for typical session

### CPU Impact
- Event dispatch: O(n) where n = subscribers
- Type checking: Negligible with frozen dataclasses
- Model updates: Initially O(m) for reset, optimizable to O(log m)

### Optimization Opportunities
1. **Batch Events:** Coalesce rapid changes
2. **Lazy Properties:** Compute on demand
3. **Incremental Updates:** Track dirty regions
4. **Event Filtering:** Subscribe to specific node IDs

## Risk Assessment

### Technical Risks
1. **Qt Model Update Complexity**
   - Mitigation: Start with reset, incremental optimization
   
2. **Event Ordering Dependencies**
   - Mitigation: Document event contracts clearly
   
3. **Performance Regression**
   - Mitigation: Benchmark before/after, profile hotspots

### Migration Risks
1. **Breaking Existing Functionality**
   - Mitigation: Comprehensive test coverage first
   
2. **Merge Conflicts**
   - Mitigation: Small, focused PRs

## Success Metrics

### Quantitative
- Zero regressions in existing tests
- < 5ms event propagation latency
- < 10% memory overhead increase
- 100% type coverage (mypy strict mode)

### Qualitative
- Cleaner separation of concerns
- Easier debugging with event tracing
- Foundation for future features (undo/redo)
- Improved code maintainability

## Timeline Estimate

- **Phase 1:** 2-3 hours (typing, events, bus)
- **Phase 2:** 3-4 hours (controller methods, tests)
- **Phase 3:** 4-6 hours (UI migration, testing)
- **Phase 4:** 2-3 hours (optimization, profiling)

**Total: 11-16 hours**

## Next Steps

1. Review and approve this plan
2. Create feature branch
3. Implement Phase 1 (foundation)
4. Submit PR for early feedback
5. Continue with subsequent phases

## Appendix: Example Usage

```python
# Before: Direct mutation
node.format.data_format = DataFormat.HEX
model.layoutChanged.emit()

# After: Controller-mediated
controller.set_node_format(
    node_id=node.instance_id,
    data_format=DataFormat.HEX
)
# Model updates automatically via event subscription
```

```python
# UI subscription example
class WaveformItemModel(QAbstractItemModel):
    def __init__(self, controller: WaveformController):
        super().__init__()
        self.controller = controller
        
        # Subscribe to relevant events
        controller.event_bus.subscribe(
            StructureChangedEvent,
            self._on_structure_changed
        )
        controller.event_bus.subscribe(
            FormatChangedEvent,
            self._on_format_changed
        )
        
    def _on_structure_changed(self, event: StructureChangedEvent):
        # Initially: full reset
        self.beginResetModel()
        self.endResetModel()
        
        # Later: fine-grained updates
        # if event.change_kind == 'move':
        #     self.beginMoveRows(...)
        #     self.endMoveRows()
```