import React from 'react';
import { View, Text, StyleSheet, Dimensions } from 'react-native';
import Markdown from 'react-native-markdown-display';
import Message from '../constants/Message';
interface Props {
  msg: Message;
  isUserMessage: boolean;
  isConsecutive: boolean;
  formatTimestamp: (ts: string) => string;
}

const { width } = Dimensions.get('window');
const MAX_BUBBLE_WIDTH = width * 0.75;

const MessageBubble: React.FC<Props> = ({ msg, isUserMessage, isConsecutive, formatTimestamp }) => (
  <View style={styles.messageRow}>
    {!isUserMessage && !isConsecutive && (
      <View style={styles.avatarContainer}>
        <View style={styles.avatar}>
          <Text style={styles.avatarText}>AI</Text>
        </View>
      </View>
    )}
    <View
      style={[
        styles.messageContainer,
        isUserMessage ? styles.userMessageContainer : styles.aiMessageContainer,
        !isUserMessage && !isConsecutive && styles.firstAiMessage,
        !isUserMessage && isConsecutive && styles.consecutiveAiMessage,
      ]}
    >
      <View
        style={[
          styles.messageBubble,
          isUserMessage ? styles.userBubble : styles.aiBubble,
          isConsecutive && styles.consecutiveBubble,
        ]}
      >
        <Markdown
          style={{
            body: { color: '#FFFFFF', fontSize: 16 },
            code_block: {
              backgroundColor: isUserMessage ? 'rgba(0,0,0,0.1)' : 'rgba(0,0,0,0.05)',
              padding: 8,
              borderRadius: 5,
            },
            code_inline: {
              backgroundColor: isUserMessage ? 'rgba(0,0,0,0.1)' : 'rgba(0,0,0,0.05)',
              padding: 4,
              borderRadius: 3,
            },
          }}
        >
          {msg.content}
        </Markdown>
      </View>
      <Text style={[styles.timestamp, isUserMessage ? styles.userTimestamp : styles.aiTimestamp]}>  
        {formatTimestamp(msg.timestamp)}
      </Text>
    </View>
  </View>
);

const styles = StyleSheet.create({
  messageRow: { flexDirection: 'row', marginVertical: 2 },
  avatarContainer: { justifyContent: 'flex-end', alignItems: 'center', marginRight: 8, paddingBottom: 15 },
  avatar: { backgroundColor: '#E1E1E1', borderRadius: 15, width: 30, height: 30, justifyContent: 'center', alignItems: 'center' },
  avatarText: { color: '#888888', fontSize: 12, fontWeight: 'bold' },
  messageContainer: { maxWidth: MAX_BUBBLE_WIDTH, marginVertical: 2, flexShrink: 1, flexWrap: 'wrap' },
  userMessageContainer: { alignSelf: 'flex-end', marginLeft: 50 },
  aiMessageContainer: { alignSelf: 'flex-start', marginRight: 50 },
  firstAiMessage: { marginTop: 8 },
  consecutiveAiMessage: { marginTop: 2 },
  messageBubble: { padding: 12, borderRadius: 18, minHeight: 36, flexShrink: 1, overflow: 'hidden' },
  userBubble: { 
    backgroundColor: '#0B84FF',
    marginLeft: 40,
    borderTopRightRadius: 4
  },
  aiBubble: { 
    backgroundColor: '#2C2C2E',
    borderTopLeftRadius: 4
  },
  consecutiveBubble: { 
    marginTop: 2,
    borderTopLeftRadius: 18,
    borderTopRightRadius: 18
  },
  timestamp: { fontSize: 10, color: '#8E8E93', paddingTop: 2, paddingHorizontal: 4 },
  userTimestamp: { alignSelf: 'flex-end' },
  aiTimestamp: { alignSelf: 'flex-start' },
});

export default MessageBubble;
