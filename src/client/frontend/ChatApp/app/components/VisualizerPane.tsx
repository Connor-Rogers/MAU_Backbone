import React, { useMemo, useRef, useEffect, useState } from 'react';
import { View, Text, ScrollView, StyleSheet } from 'react-native';
import TableVisualizer from './TableVisualizer';
import GraphVisualizer from './GraphVisualizer';
import Message from '../constants/Message';


// Show the last tool message’s visualization based on its `view` property
export default function VisualizerPane({ messages }: { messages: Message[] }) {
  // Track last tool message id/content we've processed to avoid reparsing every parent re-render (e.g. typing in prompt)
  const [parsedData, setParsedData] = useState<any>(null);
  const [view, setView] = useState<string | null>(null);
  const lastProcessedRef = useRef<string | null>(null); // timestamp-role or hash of content

  // Derive the latest tool message (scan from end for efficiency)
  const lastTool: Message | undefined = useMemo(() => {
    for (let i = messages.length - 1; i >= 0; i--) {
      if (messages[i].role === 'tool') return messages[i];
    }
    return undefined;
  }, [messages]);

  // Only (re)parse when the last tool message object actually changes (timestamp+role+content+view)
  useEffect(() => {
    if (!lastTool) return;
    const identity = `${lastTool.timestamp}|${lastTool.role}|${lastTool.view}|${lastTool.content?.length}`; // cheap identity; length change implies content change
    if (identity === lastProcessedRef.current) return; // nothing new

    if (lastTool.view == null) {
      // Clear view if tool intentionally sends null
      setView(null);
      setParsedData(null);
      lastProcessedRef.current = identity;
      return;
    }

    try {
      const parsed = JSON.parse(lastTool.content);
      setParsedData(parsed);
      setView(lastTool.view as any);
      lastProcessedRef.current = identity;
    } catch {
      setParsedData({ __error: true });
      setView('error');
      lastProcessedRef.current = identity;
    }
  }, [lastTool]);

  if (!lastTool) {
    return (
      <View style={styles.container}>
        <ScrollView contentContainerStyle={styles.content}>
          <Text style={styles.placeholder}>Awaiting tool output...</Text>
        </ScrollView>
      </View>
    );
  }

  if (view == null) {
    return null; // tool suppressed visualization
  }

  if (view === 'error' || (parsedData && parsedData.__error)) {
    return (
      <View style={styles.container}>
        <ScrollView contentContainerStyle={styles.content}>
          <Text style={styles.placeholder}>Invalid tool data</Text>
        </ScrollView>
      </View>
    );
  }

  return (
    <View style={styles.container}>
      {view === 'graph' ? (
        <ScrollView contentContainerStyle={styles.content}>
          {/* Use a stable key based on tool message timestamp so graph only rebuilds when new tool data arrives */}
          <GraphVisualizer key={lastTool.timestamp} data={parsedData as any} />
        </ScrollView>
      ) : (
        <ScrollView contentContainerStyle={styles.content}>
          <TableVisualizer data={Array.isArray(parsedData) ? parsedData : []} />
        </ScrollView>
      )}
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