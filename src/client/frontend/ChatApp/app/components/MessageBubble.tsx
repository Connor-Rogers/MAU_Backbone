import React, { useState } from 'react';
import { View, Text, StyleSheet, Dimensions, TouchableOpacity } from 'react-native';
import Markdown from 'react-native-markdown-display';
import Message from '../constants/Message';
interface Props {
  msg: Message;
  isUserMessage: boolean;
  isConsecutive: boolean;
  formatTimestamp: (ts: string) => string;
  // Marks this bubble as an intermediate explanation (not the final answer)
  isExplanation?: boolean;
  // For the very first explanation bubble in an expanded block, show section header
  showExplanationHeader?: boolean;
  // Force hiding avatar (used for explanation lists)
  suppressAvatar?: boolean;
}

const { width } = Dimensions.get('window');
const MAX_BUBBLE_WIDTH = width * 0.75;

const TRUNCATE_THRESHOLD = 380; // characters

const MessageBubble: React.FC<Props> = ({ msg, isUserMessage, isConsecutive, formatTimestamp, isExplanation, showExplanationHeader, suppressAvatar }) => {
  const [expanded, setExpanded] = useState(false);
  const needsTruncate = !!isExplanation && msg.content.length > TRUNCATE_THRESHOLD;
  const displayContent = needsTruncate && !expanded ? msg.content.slice(0, TRUNCATE_THRESHOLD) + '…' : msg.content;
  return (
  <View style={[styles.messageRow, isUserMessage && styles.userRow]}>
    {/* AI avatar (only on first AI message in a consecutive block) */}
  {!isUserMessage && !isConsecutive && !suppressAvatar && (
      <View style={styles.avatarContainer}>
        <View style={[styles.avatar, styles.aiAvatarBg]}>
          <Text style={styles.avatarText}>AI</Text>
        </View>
      </View>
    )}
    {/* User avatar (only on first user message in a consecutive block) */}
    {isUserMessage && !isConsecutive && (
      <View style={styles.userAvatarContainer}>
        <View style={[styles.avatar, styles.userAvatarBg]}>
          <Text style={styles.avatarText}>YOU</Text>
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
      {showExplanationHeader && (
        <Text style={styles.explanationHeader}>Explanation</Text>
      )}
      <View
        style={[
          styles.messageBubble,
          isUserMessage ? styles.userBubble : styles.aiBubble,
          isConsecutive && styles.consecutiveBubble,
          isExplanation && styles.explanationBubble,
        ]}
      >
  <Markdown
          style={{
            // All message text white for both user and agent
            body: { color: isExplanation ? '#DDDDDD' : '#FFFFFF', fontSize: isExplanation ? 14 : 16 },
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
          {displayContent}
        </Markdown>
        {needsTruncate && (
          <TouchableOpacity onPress={() => setExpanded(e => !e)}>
            <Text style={styles.truncateToggle}>{expanded ? 'Show less ▲' : 'Show more ▼'}</Text>
          </TouchableOpacity>
        )}
      </View>
      <Text style={[styles.timestamp, isUserMessage ? styles.userTimestamp : styles.aiTimestamp]}>  
        {formatTimestamp(msg.timestamp)}
      </Text>
    </View>
  </View>
);
};

const styles = StyleSheet.create({
  messageRow: { flexDirection: 'row', marginVertical: 2 },
  userRow: { flexDirection: 'row-reverse' },
  avatarContainer: { justifyContent: 'flex-end', alignItems: 'center', marginRight: 8, paddingBottom: 15 },
  userAvatarContainer: { justifyContent: 'flex-end', alignItems: 'center', marginLeft: 8, paddingBottom: 15 },
  avatar: { backgroundColor: '#E1E1E1', borderRadius: 15, width: 30, height: 30, justifyContent: 'center', alignItems: 'center' },
  avatarText: { color: '#FFFFFF', fontSize: 12, fontWeight: 'bold' },
  aiAvatarBg: { backgroundColor: '#666' },
  userAvatarBg: { backgroundColor: '#0B84FF' },
  messageContainer: { maxWidth: MAX_BUBBLE_WIDTH, marginVertical: 2, flexShrink: 1, flexWrap: 'wrap' },
  // Ensure user messages align to the right edge
  userMessageContainer: { marginLeft: 'auto', marginRight: 0 },
  aiMessageContainer: { alignSelf: 'flex-start', marginRight: 50 },
  firstAiMessage: { marginTop: 8 },
  consecutiveAiMessage: { marginTop: 2 },
  messageBubble: { padding: 12, borderRadius: 18, minHeight: 36, flexShrink: 1, overflow: 'hidden' },
  userBubble: { 
    backgroundColor: '#0B84FF',
    // removed extra left margin so bubble hugs right side
    borderTopRightRadius: 4
  },
  aiBubble: { 
    backgroundColor: '#444444',
    borderTopLeftRadius: 4
  },
  consecutiveBubble: { 
    marginTop: 2,
    borderTopLeftRadius: 18,
    borderTopRightRadius: 18
  },
  explanationBubble: {
    backgroundColor: '#2A2A2A',
    borderLeftWidth: 3,
    borderLeftColor: '#0FCFEC',
  },
  timestamp: { fontSize: 10, color: '#FFFFFF', paddingTop: 2, paddingHorizontal: 4 },
  userTimestamp: { alignSelf: 'flex-end' },
  aiTimestamp: { alignSelf: 'flex-start' },
  explanationHeader: {
    color: '#0FCFEC',
    fontSize: 12,
    fontWeight: '600',
    marginBottom: 4,
    marginLeft: 4,
    textTransform: 'uppercase'
  },
  truncateToggle: {
    color: '#0FCFEC',
    fontSize: 12,
    marginTop: 6,
    fontWeight: '500'
  }
});

export default MessageBubble;
