import React from 'react';
import { View, Text, ScrollView, StyleSheet } from 'react-native';

export interface TableVisualizerProps {
  data: Array<Record<string, any>>;
}

const TableVisualizer: React.FC<TableVisualizerProps> = ({ data }) => {
  // Collect all unique keys as columns
  // Collect all unique keys from data rows into a Set to determine columns
  const columnSet = new Set<string>();
  data.forEach(row => Object.keys(row).forEach(key => columnSet.add(key)));
  const columns = Array.from(columnSet);

  return (
    <ScrollView horizontal>
      <View style={styles.table}>
        {/* Header Row */}
        <View style={styles.row}>
          {columns.map(col => (
            <View key={col} style={[styles.cell, styles.headerCell]}>
              <Text style={styles.headerText} numberOfLines={1} ellipsizeMode="tail">{col}</Text>
            </View>
          ))}
        </View>
        {/* Data Rows */}
        {data.map((row, ri) => (
          <View key={ri} style={styles.row}>
            {columns.map(col => (
              <View key={col} style={styles.cell}>
                <Text style={styles.cellText} numberOfLines={1} ellipsizeMode="tail">{String(row[col] ?? '')}</Text>
              </View>
            ))}
          </View>
        ))}
      </View>
    </ScrollView>
  );
};

const styles = StyleSheet.create({
  table: { borderWidth: 1, borderColor: '#333' },
  row: { flexDirection: 'row' },
  cell: { borderWidth: 1, borderColor: '#333', width: 80, height: 80, justifyContent: 'center', alignItems: 'center', overflow: 'hidden' },
  headerCell: { backgroundColor: '#444' },
  headerText: { color: '#FFF', fontWeight: 'bold' },
  cellText: { color: '#FFF' },
});

export default TableVisualizer;
