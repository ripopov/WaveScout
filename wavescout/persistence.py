"""Persistence module for saving and loading WaveformSession state."""

import yaml
import pathlib
from typing import Dict, Any, List, Optional
from dataclasses import asdict
from .data_model import (
    WaveformSession, SignalNode, DisplayFormat, DataFormat, 
    GroupRenderMode, RenderType, Viewport, ViewportConfig, Marker, SignalNameDisplayMode, 
    AnalysisMode
)
from .waveform_db import WaveformDB


def _serialize_node(node: SignalNode) -> Dict[str, Any]:
    """Serialize a SignalNode to a dictionary, handling nested children."""
    format_dict = None
    if node.format:
        format_dict = asdict(node.format)
        # Convert enum values to strings
        if 'data_format' in format_dict and hasattr(format_dict['data_format'], 'value'):
            format_dict['data_format'] = format_dict['data_format'].value
        if 'signal_name_mode' in format_dict and hasattr(format_dict['signal_name_mode'], 'value'):
            format_dict['signal_name_mode'] = format_dict['signal_name_mode'].value
        if 'render_type' in format_dict and hasattr(format_dict['render_type'], 'value'):
            format_dict['render_type'] = format_dict['render_type'].value
        if 'analog_scaling_mode' in format_dict and hasattr(format_dict['analog_scaling_mode'], 'value'):
            format_dict['analog_scaling_mode'] = format_dict['analog_scaling_mode'].value
    
    data: Dict[str, Any] = {
        'name': node.name,
        'handle': node.handle,
        'format': format_dict,
        'nickname': node.nickname,
        'is_group': node.is_group,
        'group_render_mode': node.group_render_mode.value if node.group_render_mode else None,
        'is_expanded': node.is_expanded,
        'height_scaling': node.height_scaling,
        'is_multi_bit': node.is_multi_bit,
        'instance_id': node.instance_id,
    }
    
    # Recursively serialize children
    if node.children:
        data['children'] = [_serialize_node(child) for child in node.children]
    
    return data


def _resolve_signal_handles(nodes: List[SignalNode], waveform_db) -> None:
    """Resolve signal handles for nodes that have null handles."""
    if not waveform_db.hierarchy:
        return
        
    hierarchy = waveform_db.hierarchy
    
    # Create a cache of signal names to var objects
    name_to_var = {}
    
    # Recursively collect all vars from the hierarchy through scope iteration
    def collect_vars_from_scope(scope):
        # Add vars in this scope
        for var in scope.vars(hierarchy):
            full_name = var.full_name(hierarchy)
            name_to_var[full_name] = var
        
        # Process child scopes
        for child_scope in scope.scopes(hierarchy):
            collect_vars_from_scope(child_scope)
    
    # Start from all top scopes
    for top_scope in hierarchy.top_scopes():
        collect_vars_from_scope(top_scope)
    
    # Now we need to map var objects to handles
    # First check if waveform_db has an existing mapping (optional method)
    var_to_handle = {}
    mapping = waveform_db.get_var_to_handle_mapping()
    if mapping is not None:
        var_to_handle = mapping
    
    # If some vars are not in the existing map, we need to add them
    next_handle = waveform_db.get_next_available_handle()
    if next_handle is None:
        next_handle = 0
    for full_name, var in name_to_var.items():
        if var not in var_to_handle:
            # Note: add_var_with_handle is not implemented in WaveformDB
            # Just use the handle without adding to database
            var_to_handle[var] = next_handle
            next_handle += 1
    
    # Recursively resolve handles
    def resolve_node(node: SignalNode):
        if not node.is_group and node.handle is None:
            # Try exact match first
            if node.name in name_to_var:
                var = name_to_var[node.name]
                node.handle = var_to_handle[var]
            else:
                # Try with TOP. prefix if name doesn't already have a dot
                if '.' not in node.name:
                    prefixed_name = f"TOP.{node.name}"
                    if prefixed_name in name_to_var:
                        var = name_to_var[prefixed_name]
                        node.handle = var_to_handle[var]
                        # Update the name to the full name
                        node.name = prefixed_name
        
        # Process children
        for child in node.children:
            resolve_node(child)
    
    # Process all root nodes
    for node in nodes:
        resolve_node(node)


def _deserialize_node(data: Dict[str, Any], parent: Optional[SignalNode] = None) -> SignalNode:
    """Deserialize a dictionary to a SignalNode, handling nested children."""
    # Create display format if present
    format_data = data.get('format')
    display_format = None
    if format_data:
        # Convert string enum values back to enums
        if 'data_format' in format_data and isinstance(format_data['data_format'], str):
            format_data['data_format'] = DataFormat(format_data['data_format'])
        if 'signal_name_mode' in format_data and isinstance(format_data['signal_name_mode'], str):
            format_data['signal_name_mode'] = SignalNameDisplayMode(format_data['signal_name_mode'])
        if 'render_type' in format_data and isinstance(format_data['render_type'], str):
            format_data['render_type'] = RenderType(format_data['render_type'])
        if 'analog_scaling_mode' in format_data and isinstance(format_data['analog_scaling_mode'], str):
            from .data_model import AnalogScalingMode
            format_data['analog_scaling_mode'] = AnalogScalingMode(format_data['analog_scaling_mode'])
        display_format = DisplayFormat(**format_data)
    
    # Convert group_render_mode string back to enum
    group_render_mode = None
    if data.get('group_render_mode'):
        group_render_mode = GroupRenderMode(data['group_render_mode'])
    
    # Create node - handle backward compatibility for instance_id
    # If instance_id is not present in saved data, generate a new one
    if 'instance_id' in data:
        instance_id = data['instance_id']
    else:
        # For backward compatibility, generate a new ID
        instance_id = SignalNode._generate_id()
    
    # Create node
    node = SignalNode(
        name=data['name'],
        handle=data.get('handle'),
        format=display_format if display_format is not None else DisplayFormat(),
        nickname=data.get('nickname', ''),
        children=[],  # Will be filled below
        parent=parent,
        is_group=data.get('is_group', False),
        group_render_mode=group_render_mode,
        is_expanded=data.get('is_expanded', True),
        height_scaling=data.get('height_scaling', 1),  # Default to 1 if not present
        is_multi_bit=data.get('is_multi_bit', False),  # Default to False if not present
        instance_id=instance_id
    )
    
    # Recursively deserialize children
    children_data = data.get('children', [])
    for child_data in children_data:
        child = _deserialize_node(child_data, parent=node)
        node.children.append(child)
    
    return node


def save_session(session: WaveformSession, path: pathlib.Path):
    """
    Serialize session to YAML, excluding waveform_db pointer
    but preserving its URI for reconnection.
    """
    # Get database URI if available (file_path is an optional property)
    db_uri = None
    if session.waveform_db:
        db_uri = getattr(session.waveform_db, 'file_path', None)
    
    # Serialize data
    data = {
        'db_uri': db_uri,
        'root_nodes': [_serialize_node(node) for node in session.root_nodes],
        'viewport': asdict(session.viewport),
        'markers': [asdict(marker) for marker in session.markers],
        'cursor_time': session.cursor_time,
        'analysis_mode': asdict(session.analysis_mode),
        # Note: selected_nodes are not persisted as they are transient UI state
    }
    
    # Add timescale if available
    if session.timescale:
        data['timescale'] = {
            'factor': session.timescale.factor,
            'unit': session.timescale.unit.value
        }
    
    # Write YAML
    with open(path, 'w') as f:
        yaml.safe_dump(data, f, default_flow_style=False, sort_keys=False)


def load_session(path: pathlib.Path) -> WaveformSession:
    """
    Deserialize YAML to dataclasses and reconnect to waveform DB.
    """
    # Read YAML
    with open(path, 'r') as f:
        data = yaml.safe_load(f)
    
    # Reconnect to waveform database if URI is provided
    waveform_db = None
    db_uri = data.get('db_uri')
    if db_uri and pathlib.Path(db_uri).exists():
        waveform_db = WaveformDB()
        waveform_db.open(db_uri)
    
    # Deserialize viewport
    viewport_data = data.get('viewport', {})
    # Extract config data and create ViewportConfig object
    config_data = viewport_data.pop('config', {})
    viewport_config = ViewportConfig(**config_data)
    # Create viewport with proper config object
    viewport = Viewport(**viewport_data, config=viewport_config)
    
    # Deserialize markers
    markers = []
    for marker_data in data.get('markers', []):
        markers.append(Marker(**marker_data))
    
    # Deserialize analysis mode
    analysis_data = data.get('analysis_mode', {})
    analysis_mode = AnalysisMode(**analysis_data)
    
    # Deserialize nodes
    root_nodes = []
    for node_data in data.get('root_nodes', []):
        node = _deserialize_node(node_data)
        root_nodes.append(node)
    
    # Create session
    session = WaveformSession(
        waveform_db=waveform_db,
        root_nodes=root_nodes,
        viewport=viewport,
        markers=markers,
        cursor_time=data.get('cursor_time', 0),
        analysis_mode=analysis_mode,
        selected_nodes=[]  # Start with empty selection
    )
    
    # Restore timescale if available
    timescale_data = data.get('timescale')
    if timescale_data:
        from .data_model import TimeUnit, Timescale
        unit = TimeUnit.from_string(timescale_data['unit'])
        if unit:
            session.timescale = Timescale(
                factor=timescale_data['factor'],
                unit=unit
            )
    # If timescale not in saved data but waveform_db is loaded, get it from there
    elif waveform_db:
        session.timescale = waveform_db.get_timescale()
    
    # Resolve signal handles if waveform_db is available
    if waveform_db:
        _resolve_signal_handles(session.root_nodes, waveform_db)
        
        # Update viewport total_duration from the waveform's time table
        time_table = waveform_db.get_time_table()
        if time_table and len(time_table) > 0:
            # The last time in the time table is the total duration in timescale units
            session.viewport.total_duration = time_table[-1]
    
    # Update the SignalNode counter to avoid ID conflicts
    # Find the maximum instance_id in all loaded nodes
    def find_max_instance_id(nodes):
        max_id = 0
        for node in nodes:
            if getattr(node, 'instance_id', None) is not None:
                max_id = max(max_id, node.instance_id)
            if node.children:
                max_id = max(max_id, find_max_instance_id(node.children))
        return max_id
    
    max_instance_id = find_max_instance_id(root_nodes)
    if max_instance_id > 0:
        SignalNode._id_counter = max_instance_id
    
    return session