import { Stack } from "expo-router";

export default function RootLayout() {
  return (
    // Disable default header for dark Command Center style
    <Stack
      screenOptions={{
        headerShown: false,
        // Optionally, to use a black header bar instead of hiding:
        // headerStyle: { backgroundColor: '#000' },
        // headerTintColor: '#fff',
      }}
    />
  );
}
