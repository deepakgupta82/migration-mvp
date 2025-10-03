"""
Diagram Entity Extractor (Issue #11)

Extracts entities and relationships from architecture diagrams.
Uses MinerU diagram metadata (bounding boxes, OCR text) from JSONL.

Key features:
- Diagram element extraction (boxes, circles, arrows)
- Entity inference from shape text (OCR)
- Spatial relationship detection (proximity, alignment)
- Arrow-based connectivity inference
- Entity type classification (server, database, service, etc.)

Example usage:
    extractor = DiagramEntityExtractor()
    result = extractor.extract_from_diagram_elements(elements)
    entities = result['entities']
    relationships = result['relationships']
"""
import logging
import re
from typing import Dict, Any, List, Tuple, Optional
from dataclasses import dataclass
from enum import Enum

logger = logging.getLogger(__name__)


class ShapeType(Enum):
    """Common diagram shape types."""
    RECTANGLE = "rectangle"
    CIRCLE = "circle"
    DIAMOND = "diamond"
    ARROW = "arrow"
    LINE = "line"
    TEXT = "text"
    UNKNOWN = "unknown"


@dataclass
class DiagramElement:
    """Represents a diagram element with spatial info."""
    element_id: str
    shape_type: ShapeType
    text: str
    bbox: Tuple[float, float, float, float]  # x1, y1, x2, y2
    page_number: int
    metadata: Dict[str, Any]


@dataclass
class DiagramExtractionResult:
    """Result of diagram entity extraction."""
    entities: List[Dict[str, Any]]
    relationships: List[Dict[str, Any]]
    stats: Dict[str, Any]


class DiagramEntityExtractor:
    """
    Extracts entities and relationships from architecture diagrams.
    
    Extraction strategies:
    1. OCR text analysis (server names, component labels)
    2. Shape type inference (rectangles = servers, cylinders = databases)
    3. Spatial proximity (nearby elements likely related)
    4. Arrow detection (explicit connections)
    5. Vertical/horizontal alignment (logical grouping)
    """
    
    # Entity type keywords
    ENTITY_KEYWORDS = {
        'server': [r'(?i)server', r'(?i)host', r'(?i)vm', r'(?i)instance'],
        'database': [r'(?i)database', r'(?i)db', r'(?i)sql', r'(?i)oracle', r'(?i)mysql', r'(?i)postgres'],
        'application': [r'(?i)app', r'(?i)service', r'(?i)api', r'(?i)microservice'],
        'storage': [r'(?i)storage', r'(?i)disk', r'(?i)volume', r'(?i)s3', r'(?i)blob'],
        'network': [r'(?i)network', r'(?i)router', r'(?i)switch', r'(?i)firewall', r'(?i)lb', r'(?i)load\s*balancer'],
        'cloud': [r'(?i)cloud', r'(?i)aws', r'(?i)azure', r'(?i)gcp', r'(?i)k8s', r'(?i)kubernetes'],
        'user': [r'(?i)user', r'(?i)client', r'(?i)browser', r'(?i)mobile'],
    }
    
    # Proximity threshold (pixels or relative units)
    PROXIMITY_THRESHOLD = 100
    
    # Alignment threshold (pixels)
    ALIGNMENT_THRESHOLD = 20
    
    def __init__(self):
        """Initialize extractor."""
        self.extracted_entities = []
        self.extracted_relationships = []
    
    def extract_from_jsonl_elements(
        self,
        jsonl_elements: List[Dict[str, Any]],
        infer_spatial_relationships: bool = True
    ) -> DiagramExtractionResult:
        """
        Extract entities from JSONL diagram elements.
        
        Args:
            jsonl_elements: List of JSONL element dicts (from MinerU)
            infer_spatial_relationships: If True, infer relationships from spatial proximity
        
        Returns:
            DiagramExtractionResult with entities and relationships
        """
        # Filter diagram-related elements
        diagram_elements = self._filter_diagram_elements(jsonl_elements)
        
        if not diagram_elements:
            logger.info("No diagram elements found in JSONL")
            return DiagramExtractionResult(
                entities=[],
                relationships=[],
                stats={'diagram_elements': 0, 'entities': 0, 'relationships': 0}
            )
        
        # Convert to DiagramElement objects
        parsed_elements = self._parse_diagram_elements(diagram_elements)
        
        # Extract entities from diagram shapes
        entities = self._extract_entities_from_shapes(parsed_elements)
        
        # Extract explicit relationships (arrows, lines)
        explicit_relationships = self._extract_explicit_relationships(parsed_elements)
        
        # Infer spatial relationships
        spatial_relationships = []
        if infer_spatial_relationships:
            spatial_relationships = self._infer_spatial_relationships(entities, parsed_elements)
        
        # Combine relationships
        all_relationships = explicit_relationships + spatial_relationships
        
        # Deduplicate relationships
        unique_relationships = self._deduplicate_relationships(all_relationships)
        
        # Build stats
        stats = {
            'diagram_elements': len(diagram_elements),
            'parsed_elements': len(parsed_elements),
            'entities': len(entities),
            'explicit_relationships': len(explicit_relationships),
            'spatial_relationships': len(spatial_relationships),
            'total_relationships': len(unique_relationships)
        }
        
        logger.info(
            f"Diagram extraction complete: {stats['entities']} entities, "
            f"{stats['total_relationships']} relationships from {stats['diagram_elements']} diagram elements"
        )
        
        return DiagramExtractionResult(
            entities=entities,
            relationships=unique_relationships,
            stats=stats
        )
    
    def _filter_diagram_elements(
        self,
        jsonl_elements: List[Dict[str, Any]]
    ) -> List[Dict[str, Any]]:
        """Filter elements that are likely from diagrams."""
        diagram_elements = []
        
        for element in jsonl_elements:
            element_data = element.get('data', {}) if 'data' in element else element
            element_type = element_data.get('type', '').lower()
            metadata = element_data.get('metadata', {})
            
            # Check for diagram indicators
            is_diagram = False
            
            # Type-based detection
            if element_type in ('image', 'figure', 'diagram', 'chart'):
                is_diagram = True
            
            # Metadata-based detection
            if metadata.get('is_diagram', False):
                is_diagram = True
            
            # Filename-based detection
            text = element_data.get('text', '')
            if any(keyword in text.lower() for keyword in ['architecture', 'topology', 'diagram', 'flow']):
                is_diagram = True
            
            # Has bounding boxes (spatial layout)
            coordinates = element_data.get('coordinates')
            if coordinates and isinstance(coordinates, dict):
                if all(k in coordinates for k in ['x1', 'y1', 'x2', 'y2']):
                    # Elements with precise coordinates might be diagram components
                    # But we need additional context to be sure
                    pass
            
            if is_diagram:
                diagram_elements.append(element_data)
        
        return diagram_elements
    
    def _parse_diagram_elements(
        self,
        diagram_elements: List[Dict[str, Any]]
    ) -> List[DiagramElement]:
        """Parse diagram elements into DiagramElement objects."""
        parsed = []
        
        for elem in diagram_elements:
            try:
                element_id = elem.get('element_id', f"diagram_elem_{len(parsed)}")
                text = elem.get('text', '')
                page_number = elem.get('page_number', 1)
                coordinates = elem.get('coordinates', {})
                metadata = elem.get('metadata', {})
                
                # Extract bounding box
                bbox = (
                    coordinates.get('x1', 0),
                    coordinates.get('y1', 0),
                    coordinates.get('x2', 0),
                    coordinates.get('y2', 0)
                )
                
                # Infer shape type (simple heuristic)
                shape_type = self._infer_shape_type(elem, bbox)
                
                diagram_elem = DiagramElement(
                    element_id=element_id,
                    shape_type=shape_type,
                    text=text,
                    bbox=bbox,
                    page_number=page_number,
                    metadata=metadata
                )
                
                parsed.append(diagram_elem)
            
            except Exception as e:
                logger.warning(f"Failed to parse diagram element: {e}")
                continue
        
        return parsed
    
    def _infer_shape_type(
        self,
        element: Dict[str, Any],
        bbox: Tuple[float, float, float, float]
    ) -> ShapeType:
        """Infer shape type from element properties."""
        element_type = element.get('type', '').lower()
        text = element.get('text', '').lower()
        
        # Check for arrow/line indicators
        if 'arrow' in text or '->' in text or '=>' in text:
            return ShapeType.ARROW
        
        # Check for explicit shape metadata
        metadata = element.get('metadata', {})
        shape_hint = metadata.get('shape', metadata.get('shape_type', '')).lower()
        
        if 'arrow' in shape_hint or 'line' in shape_hint:
            return ShapeType.ARROW
        if 'circle' in shape_hint or 'ellipse' in shape_hint:
            return ShapeType.CIRCLE
        if 'diamond' in shape_hint or 'rhombus' in shape_hint:
            return ShapeType.DIAMOND
        if 'rectangle' in shape_hint or 'box' in shape_hint:
            return ShapeType.RECTANGLE
        
        # Infer from aspect ratio
        x1, y1, x2, y2 = bbox
        width = x2 - x1
        height = y2 - y1
        
        if width > 0 and height > 0:
            aspect_ratio = width / height
            
            # Long horizontal or vertical lines
            if aspect_ratio > 5 or aspect_ratio < 0.2:
                return ShapeType.LINE
            
            # Nearly square shapes
            if 0.8 <= aspect_ratio <= 1.2:
                return ShapeType.CIRCLE
            
            # Default to rectangle
            return ShapeType.RECTANGLE
        
        return ShapeType.UNKNOWN
    
    def _extract_entities_from_shapes(
        self,
        diagram_elements: List[DiagramElement]
    ) -> List[Dict[str, Any]]:
        """Extract entities from diagram shapes."""
        entities = []
        
        for elem in diagram_elements:
            # Skip connectors (arrows, lines)
            if elem.shape_type in (ShapeType.ARROW, ShapeType.LINE):
                continue
            
            # Extract entity from shape text
            if not elem.text or len(elem.text.strip()) < 2:
                continue
            
            # Infer entity type from text
            entity_type = self._infer_entity_type(elem.text)
            
            entity = {
                'entity_id': f"diagram_{elem.element_id}",
                'entity_type': entity_type,
                'name': elem.text.strip()[:100],  # Limit name length
                'attributes': {
                    'source': 'diagram',
                    'shape_type': elem.shape_type.value,
                    'page_number': elem.page_number,
                    'bbox': elem.bbox,
                    'diagram_element_id': elem.element_id
                }
            }
            
            entities.append(entity)
        
        return entities
    
    def _infer_entity_type(self, text: str) -> str:
        """Infer entity type from text content."""
        text_lower = text.lower()
        
        for entity_type, patterns in self.ENTITY_KEYWORDS.items():
            for pattern in patterns:
                if re.search(pattern, text_lower):
                    return entity_type
        
        # Default to component
        return 'component'
    
    def _extract_explicit_relationships(
        self,
        diagram_elements: List[DiagramElement]
    ) -> List[Dict[str, Any]]:
        """Extract relationships from arrows and connectors."""
        relationships = []
        
        # Find arrow/line elements
        connectors = [e for e in diagram_elements if e.shape_type in (ShapeType.ARROW, ShapeType.LINE)]
        
        # Find shape elements (potential entities)
        shapes = [e for e in diagram_elements if e.shape_type not in (ShapeType.ARROW, ShapeType.LINE)]
        
        # For each connector, find source and target shapes
        for connector in connectors:
            # Find shapes near connector endpoints
            source_shape = self._find_nearest_shape(connector.bbox[:2], shapes)  # Start point
            target_shape = self._find_nearest_shape(connector.bbox[2:], shapes)  # End point
            
            if source_shape and target_shape and source_shape != target_shape:
                relationship = {
                    'source_id': f"diagram_{source_shape.element_id}",
                    'target_id': f"diagram_{target_shape.element_id}",
                    'relationship_type': 'CONNECTED_TO',
                    'properties': {
                        'source': 'diagram_arrow',
                        'connector_id': connector.element_id
                    }
                }
                relationships.append(relationship)
        
        return relationships
    
    def _find_nearest_shape(
        self,
        point: Tuple[float, float],
        shapes: List[DiagramElement],
        max_distance: float = 50
    ) -> Optional[DiagramElement]:
        """Find nearest shape to a point."""
        x, y = point
        nearest = None
        min_distance = max_distance
        
        for shape in shapes:
            # Calculate center of shape
            x1, y1, x2, y2 = shape.bbox
            center_x = (x1 + x2) / 2
            center_y = (y1 + y2) / 2
            
            # Calculate distance
            distance = ((x - center_x) ** 2 + (y - center_y) ** 2) ** 0.5
            
            if distance < min_distance:
                min_distance = distance
                nearest = shape
        
        return nearest
    
    def _infer_spatial_relationships(
        self,
        entities: List[Dict[str, Any]],
        diagram_elements: List[DiagramElement]
    ) -> List[Dict[str, Any]]:
        """Infer relationships based on spatial proximity."""
        relationships = []
        
        # Build entity ID to element map
        entity_to_elem = {}
        for elem in diagram_elements:
            entity_id = f"diagram_{elem.element_id}"
            entity_to_elem[entity_id] = elem
        
        # Check proximity between entities
        for i, entity1 in enumerate(entities):
            for entity2 in entities[i+1:]:
                entity1_id = entity1['entity_id']
                entity2_id = entity2['entity_id']
                
                if entity1_id not in entity_to_elem or entity2_id not in entity_to_elem:
                    continue
                
                elem1 = entity_to_elem[entity1_id]
                elem2 = entity_to_elem[entity2_id]
                
                # Calculate proximity
                distance = self._calculate_distance(elem1.bbox, elem2.bbox)
                
                if distance < self.PROXIMITY_THRESHOLD:
                    relationship = {
                        'source_id': entity1_id,
                        'target_id': entity2_id,
                        'relationship_type': 'NEAR',
                        'properties': {
                            'source': 'spatial_proximity',
                            'distance': round(distance, 2)
                        }
                    }
                    relationships.append(relationship)
        
        return relationships
    
    def _calculate_distance(
        self,
        bbox1: Tuple[float, float, float, float],
        bbox2: Tuple[float, float, float, float]
    ) -> float:
        """Calculate distance between two bounding boxes (center-to-center)."""
        x1_center = (bbox1[0] + bbox1[2]) / 2
        y1_center = (bbox1[1] + bbox1[3]) / 2
        
        x2_center = (bbox2[0] + bbox2[2]) / 2
        y2_center = (bbox2[1] + bbox2[3]) / 2
        
        distance = ((x1_center - x2_center) ** 2 + (y1_center - y2_center) ** 2) ** 0.5
        
        return distance
    
    def _deduplicate_relationships(
        self,
        relationships: List[Dict[str, Any]]
    ) -> List[Dict[str, Any]]:
        """Remove duplicate relationships."""
        seen = set()
        unique = []
        
        for rel in relationships:
            key = (rel['source_id'], rel['target_id'], rel['relationship_type'])
            if key not in seen:
                seen.add(key)
                unique.append(rel)
        
        return unique


def extract_diagram_entities(
    jsonl_elements: List[Dict[str, Any]],
    infer_spatial_relationships: bool = True
) -> Dict[str, Any]:
    """
    Convenience function to extract entities from diagram elements.
    
    Args:
        jsonl_elements: List of JSONL element dicts
        infer_spatial_relationships: If True, infer spatial relationships
    
    Returns:
        Dict with extraction results
    """
    extractor = DiagramEntityExtractor()
    result = extractor.extract_from_jsonl_elements(jsonl_elements, infer_spatial_relationships)
    
    return {
        'entities': result.entities,
        'relationships': result.relationships,
        'stats': result.stats
    }
