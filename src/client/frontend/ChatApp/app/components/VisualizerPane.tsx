import React, { useState, useEffect } from 'react';
import { View, Text, ScrollView, StyleSheet } from 'react-native';
import TableVisualizer from './TableVisualizer';
import Message from '../constants/Message';


// Show the last tool message’s visualization based on its `view` property
export default function VisualizerPane({ messages }: { messages: Message[] }) {
  // Find last tool message
  const toolMsgs = messages.filter(m => m.role === 'tool');
  if (!toolMsgs.length) {
    return (
      <View style={styles.container}>
        <ScrollView contentContainerStyle={styles.content}>
          <Text style={styles.placeholder}>Awaiting tool output...</Text>
        </ScrollView>
      </View>
    );
  }
  const lastTool = toolMsgs[toolMsgs.length - 1];
  let parsed: Array<Record<string, any>> = [];
  try {
    parsed = JSON.parse(lastTool.content);
  } catch {
    return (
      <View style={styles.container}>
        <Text style={styles.placeholder}>Invalid tool data</Text>
      </View>
    );
  }
  const view = lastTool.view;
  return (
    <View style={styles.container}>
      <ScrollView contentContainerStyle={styles.content}>
        {view === 'graph' ? (
          <Text style={styles.placeholder}>Graph view not implemented</Text>
        ) : (
          <TableVisualizer data={parsed} />
        )}
      </ScrollView>
    </View>
  );
}

const styles = StyleSheet.create({
  container: {
    flex: 1,
    backgroundColor: '#0D0D0D',
    borderLeftWidth: 1,
    borderLeftColor: '#333',
  },
  content: {
    padding: 12,
  },
  placeholder: {
    color: '#555',
    fontStyle: 'italic',
  },
});