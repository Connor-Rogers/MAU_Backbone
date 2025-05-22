import React from 'react';
import { View, Text, ScrollView, StyleSheet } from 'react-native';

export default function VisualizerPane() {
  return (
    <View style={styles.container}>
      <ScrollView contentContainerStyle={styles.content}>
        <Text style={styles.placeholder}>Awaiting tool output...</Text>
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