import { StatusBar } from 'expo-status-bar'
import { StyleSheet, Text, View } from 'react-native'

import { colors, space } from '@/theme'

/** Application shell. Screens are added as the API grows. */
export function App() {
  return (
    <View style={styles.container}>
      <Text accessibilityRole="header" style={styles.title}>
        Task Master
      </Text>
      <Text style={styles.tagline}>
        Goal-driven tasks that beat procrastination.
      </Text>
      <StatusBar style="light" />
    </View>
  )
}

const styles = StyleSheet.create({
  container: {
    flex: 1,
    backgroundColor: colors.bg,
    alignItems: 'center',
    justifyContent: 'center',
    padding: space[4],
  },
  title: { color: colors.text, fontSize: 28, fontWeight: '700' },
  tagline: { color: colors.textMuted, marginTop: space[2] },
})
