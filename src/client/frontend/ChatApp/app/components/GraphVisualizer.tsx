import React, { useState, useEffect, useRef } from 'react';
import { View, StyleSheet, Dimensions, PanResponder, Text, TouchableOpacity, Pressable } from 'react-native';
import Svg, { Circle, Line, G } from 'react-native-svg';
import * as d3 from 'd3-force';

export interface GraphData {
  nodes: Array<{ id: string; [key: string]: any }>;
  edges: Array<{ source: string; target: string; [key: string]: any }>;
}

export interface GraphVisualizerProps {
  data: GraphData;
}

const GraphVisualizer: React.FC<GraphVisualizerProps> = ({ data }) => {
  const { width, height } = Dimensions.get('window');
  const [nodes, setNodes] = useState<any[]>([]);
  const [links, setLinks] = useState<any[]>([]);
  const [scale, setScale] = useState(1);
  const [translateX, setTranslateX] = useState(0);
  const [translateY, setTranslateY] = useState(0);
  const [selectedNode, setSelectedNode] = useState<any>(null);
  const [selectedEdge, setSelectedEdge] = useState<any>(null);
  const [hoveredNode, setHoveredNode] = useState<any>(null);
  const [hoveredEdge, setHoveredEdge] = useState<any>(null);
  const simulationRef = useRef<any>(null);
  const lastTapRef = useRef(0);

  useEffect(() => {
    // Initialize force simulation
    const simulation = d3
      .forceSimulation(data.nodes)
      .force('link', d3.forceLink(data.edges).id((d: any) => d.id).distance(120))
      .force('charge', d3.forceManyBody().strength(-400))
      .force('center', d3.forceCenter(width / 2, height / 2))
      .force('collision', d3.forceCollide().radius(25))
      .on('tick', () => {
        setNodes([...simulation.nodes()]);
        setLinks([...data.edges] as any);
      });

    simulationRef.current = simulation;
    
    return () => {
      simulation.stop();
    };
  }, [data, width, height]);

  // Pan responder for zoom and pan
  const panResponder = PanResponder.create({
    onStartShouldSetPanResponder: () => true,
    onMoveShouldSetPanResponder: (evt, gestureState) => {
      // Only capture if it's a significant movement or multi-touch
      return Math.abs(gestureState.dx) > 10 || Math.abs(gestureState.dy) > 10 || evt.nativeEvent.touches.length > 1;
    },
    
    onPanResponderGrant: (evt) => {
      const now = Date.now();
      const timeDiff = now - lastTapRef.current;
      lastTapRef.current = now;
      
      // Double tap to reset zoom
      if (timeDiff < 300) {
        setScale(1);
        setTranslateX(0);
        setTranslateY(0);
      }
    },
    
    onPanResponderMove: (evt, gestureState) => {
      // Check if it's a pinch gesture (multiple touches)
      if (evt.nativeEvent.touches.length === 2) {
        // Simple zoom based on gesture
        const newScale = Math.max(0.5, Math.min(3, scale + gestureState.dy * 0.01));
        setScale(newScale);
      } else {
        // Pan gesture
        setTranslateX(translateX + gestureState.dx);
        setTranslateY(translateY + gestureState.dy);
      }
    },
  });

  // Node drag functionality
  const handleNodePress = (node: any, evt: any) => {
    setSelectedNode(node);
    setSelectedEdge(null); // Clear edge selection when selecting node
    
    // Start dragging
    if (simulationRef.current) {
      simulationRef.current.alphaTarget(0.3).restart();
      node.fx = node.x;
      node.fy = node.y;
    }
  };

  const handleNodeDrag = (node: any, gestureState: any) => {
    if (simulationRef.current && selectedNode?.id === node.id) {
      node.fx = node.x + gestureState.dx / scale;
      node.fy = node.y + gestureState.dy / scale;
    }
  };

  const handleNodeRelease = (node: any) => {
    if (simulationRef.current) {
      simulationRef.current.alphaTarget(0);
      node.fx = null;
      node.fy = null;
    }
    // Keep node selected for info display
  };

  // Edge click functionality
  const handleEdgeClick = (edge: any) => {
    console.log('Edge clicked:', edge.id || `${edge.source.id} -> ${edge.target.id}`);
    setSelectedEdge(edge);
    setSelectedNode(null); // Clear node selection when selecting edge
  };

  // Edge hover functionality
  const handleEdgeHover = (edge: any) => {
    setHoveredEdge(edge);
  };

  const handleEdgeHoverEnd = () => {
    setHoveredEdge(null);
  };

  // Node click functionality (without drag)
  const handleNodeClick = (node: any) => {
    console.log('Node clicked:', node.id);
    setSelectedNode(selectedNode?.id === node.id ? null : node); // Toggle selection
    setSelectedEdge(null); // Clear edge selection
  };

  // Create individual pan responders for each node
  const createNodePanResponder = (node: any) => {
    let isDragging = false;
    let startTime = 0;
    
    return PanResponder.create({
      onStartShouldSetPanResponder: () => true,
      onMoveShouldSetPanResponder: () => true,
      
      onPanResponderGrant: (evt) => {
        startTime = Date.now();
        isDragging = false;
        handleNodePress(node, evt);
      },
      
      onPanResponderMove: (evt, gestureState) => {
        const moveDistance = Math.sqrt(gestureState.dx * gestureState.dx + gestureState.dy * gestureState.dy);
        if (moveDistance > 5) {
          isDragging = true;
          handleNodeDrag(node, gestureState);
        }
      },
      
      onPanResponderRelease: () => {
        const duration = Date.now() - startTime;
        if (!isDragging && duration < 200) {
          // It was a quick tap, treat as click
          handleNodeClick(node);
        }
        handleNodeRelease(node);
      },
    });
  };

  return (
    <View style={styles.container}>
      <View {...panResponder.panHandlers} style={styles.svgContainer}>
        <Svg width={width} height={height}>
          <G
            scale={scale}
            translateX={translateX}
            translateY={translateY}
          >
            {/* Render links */}
            {links.map((link: any, i: number) => {
              const isSelected = selectedEdge === link;
              const isHovered = hoveredEdge === link;
              
              return (
                <G key={`link-${i}`}>
                  {/* Visible edge */}
                  <Line
                    x1={link.source.x || 0}
                    y1={link.source.y || 0}
                    x2={link.target.x || 0}
                    y2={link.target.y || 0}
                    stroke={isSelected ? "#FF6B6B" : isHovered ? "#4ECDC4" : "#999"}
                    strokeWidth={isSelected ? 8 : isHovered ? 6 : 4}
                    strokeOpacity={isSelected ? 1 : 0.8}
                  />
                </G>
              );
            })}
            
            {/* Render nodes */}
            {nodes.map((node: any, i: number) => {
              const isSelected = selectedNode?.id === node.id;
              const isHovered = hoveredNode?.id === node.id;
              
              return (
                <G key={`node-${i}`}>
                  {/* Visible node */}
                  <Circle
                    cx={node.x || 0}
                    cy={node.y || 0}
                    r={isSelected ? 20 : isHovered ? 16 : 12}
                    fill={isSelected ? "#FF6B6B" : isHovered ? "#4ECDC4" : "#0FCFEC"}
                    stroke={isSelected ? "#FF4757" : "#fff"}
                    strokeWidth={isSelected ? 4 : 3}
                    opacity={selectedNode && !isSelected ? 0.6 : 1}
                  />
                </G>
              );
            })}
          </G>
        </Svg>
      </View>
      
      {/* Overlay Pressable elements for node interactions */}
      {nodes.map((node: any, i: number) => {
        const transformedX = ((node.x || 0) * scale) + translateX;
        const transformedY = ((node.y || 0) * scale) + translateY;

        return (
          <Pressable
            key={`node-overlay-${i}`}
            style={[
              styles.nodeOverlay,
              {
                left: transformedX - 25,
                top: transformedY - 25,
              },
            ]}
            onPress={() => handleNodeClick(node)}
            onPressIn={() => setHoveredNode(node)}
            onPressOut={() => setHoveredNode(null)}
          />
        );
      })}

      {/* Overlay Pressable elements for edge interactions */}
      {links.map((link: any, i: number) => {
        const sourceX = ((link.source.x || 0) * scale) + translateX;
        const sourceY = ((link.source.y || 0) * scale) + translateY;
        const targetX = ((link.target.x || 0) * scale) + translateX;
        const targetY = ((link.target.y || 0) * scale) + translateY;

        const midX = (sourceX + targetX) / 2;
        const midY = (sourceY + targetY) / 2;
        const length = Math.sqrt(Math.pow(targetX - sourceX, 2) + Math.pow(targetY - sourceY, 2));
        const angle = Math.atan2(targetY - sourceY, targetX - sourceX) * 180 / Math.PI;

        return (
          <Pressable
            key={`edge-overlay-${i}`}
            style={[
              styles.edgeOverlay,
              {
                left: midX - length / 2,
                top: midY - 10,
                width: length,
                transform: [{ rotate: `${angle}deg` }],
              },
            ]}
            onPress={() => handleEdgeClick(link)}
            onPressIn={() => setHoveredEdge(link)}
            onPressOut={() => setHoveredEdge(null)}
          />
        );
      })}
      
      {/* Info panel for nodes and edges */}
      {(selectedNode || selectedEdge || hoveredNode || hoveredEdge) && (
        <View style={styles.infoPanel}>
          <TouchableOpacity 
            style={styles.closeButton}
            onPress={() => {
              setSelectedNode(null);
              setSelectedEdge(null);
              setHoveredNode(null);
              setHoveredEdge(null);
            }}
          >
            <Text style={styles.closeButtonText}>✕</Text>
          </TouchableOpacity>
          
          {(selectedNode || hoveredNode) && (
            <>
              <Text style={styles.infoTitle}>
                {selectedNode ? 'Selected Node: ' : 'Hovered Node: '}
                {(selectedNode || hoveredNode)?.id}
              </Text>
              {Object.keys((selectedNode || hoveredNode) || {})
                .filter(key => key !== 'id' && key !== 'x' && key !== 'y' && key !== 'fx' && key !== 'fy' && key !== 'index' && key !== 'vx' && key !== 'vy')
                .map(key => (
                  <Text key={key} style={styles.infoText}>
                    <Text style={styles.infoKey}>{key}:</Text> {JSON.stringify((selectedNode || hoveredNode)?.[key])}
                  </Text>
                ))}
            </>
          )}
          
          {(selectedEdge || hoveredEdge) && (
            <>
              <Text style={styles.infoTitle}>
                {selectedEdge ? 'Selected Edge: ' : 'Hovered Edge: '}
                {(selectedEdge || hoveredEdge)?.source?.id || (selectedEdge || hoveredEdge)?.source} → {(selectedEdge || hoveredEdge)?.target?.id || (selectedEdge || hoveredEdge)?.target}
              </Text>
              {Object.keys((selectedEdge || hoveredEdge) || {})
                .filter(key => key !== 'source' && key !== 'target' && key !== 'index')
                .map(key => (
                  <Text key={key} style={styles.infoText}>
                    <Text style={styles.infoKey}>{key}:</Text> {JSON.stringify((selectedEdge || hoveredEdge)?.[key])}
                  </Text>
                ))}
            </>
          )}
        </View>
      )}
      
      {/* Instructions */}
      <View style={styles.instructions}>
        <Text style={styles.instructionText}>
          • Tap large nodes/edges to see info
        </Text>
        <Text style={styles.instructionText}>
          • Drag nodes to reposition
        </Text>
        <Text style={styles.instructionText}>
          • Double tap to reset zoom
        </Text>
        <Text style={styles.instructionText}>
          • Pinch to zoom
        </Text>
      </View>
      
      {/* Hovered node or edge label */}
      {(hoveredNode || hoveredEdge) && (
        <Text
          style={[
            styles.hoverLabel,
            hoveredNode
              ? {
                  left: ((hoveredNode.x || 0) * scale) + translateX,
                  top: ((hoveredNode.y || 0) * scale) + translateY - 20,
                }
              : {
                  left: (((hoveredEdge.source.x || 0) + (hoveredEdge.target.x || 0)) / 2) * scale + translateX,
                  top: (((hoveredEdge.source.y || 0) + (hoveredEdge.target.y || 0)) / 2) * scale + translateY - 20,
                },
          ]}
        >
          {hoveredNode ? hoveredNode.id : `${hoveredEdge.source.id} → ${hoveredEdge.target.id}`}
        </Text>
      )}
    </View>
  );
};

const styles = StyleSheet.create({
  container: { 
    flex: 1,
    backgroundColor: '#000',
  },
  svgContainer: {
    flex: 1,
  },
  infoPanel: {
    position: 'absolute',
    top: 10,
    left: 10,
    backgroundColor: 'rgba(0, 0, 0, 0.8)',
    padding: 10,
    borderRadius: 8,
    borderColor: '#0FCFEC',
    borderWidth: 1,
    maxWidth: 200,
  },
  infoTitle: {
    color: '#0FCFEC',
    fontSize: 14,
    fontWeight: 'bold',
    marginBottom: 5,
  },
  infoText: {
    color: '#CCCCCC',
    fontSize: 12,
    marginBottom: 2,
  },
  infoKey: {
    color: '#0FCFEC',
    fontWeight: 'bold',
  },
  closeButton: {
    position: 'absolute',
    top: 5,
    right: 5,
    width: 20,
    height: 20,
    justifyContent: 'center',
    alignItems: 'center',
    backgroundColor: 'rgba(255, 107, 107, 0.2)',
    borderRadius: 10,
  },
  closeButtonText: {
    color: '#FF6B6B',
    fontSize: 12,
    fontWeight: 'bold',
  },
  instructions: {
    position: 'absolute',
    bottom: 10,
    right: 10,
    backgroundColor: 'rgba(0, 0, 0, 0.8)',
    padding: 8,
    borderRadius: 6,
    borderColor: '#333',
    borderWidth: 1,
  },
  instructionText: {
    color: '#888',
    fontSize: 10,
    marginBottom: 2,
  },
  nodeOverlay: {
    position: 'absolute',
    width: 50,
    height: 50,
    backgroundColor: 'transparent',
    borderRadius: 25,
    zIndex: 10,
  },
  edgeOverlay: {
    position: 'absolute',
    height: 20,
    backgroundColor: 'transparent',
    zIndex: 5,
  },
  hoverLabel: {
    position: 'absolute',
    backgroundColor: 'rgba(0, 0, 0, 0.7)',
    color: '#FFF',
    paddingHorizontal: 6,
    paddingVertical: 2,
    borderRadius: 4,
    fontSize: 12,
    textAlign: 'center',
    transform: [{ translateX: -50 }], // Center the label horizontally
  },
});

export default GraphVisualizer;
