import App from "./App";
import { StyleSheet, View } from 'react-native';
export default function Index() {
  return (
    <View style={styles.container}>
      <App />
    </View>
  );
}

const styles = StyleSheet.create({
  container: {
    flex: 1,
    backgroundColor: '#000',
    height: '100%', // Works on both web and native
  }
});
