import React, { useEffect, useState, useRef } from 'react';
import { 
  SafeAreaView, 
  View, 
  Text, 
  TextInput, 
  TouchableOpacity, 
  ScrollView, 
  StyleSheet, 
  ActivityIndicator, 
  Platform,
  KeyboardAvoidingView,
  Dimensions,
  NativeSyntheticEvent,
  TextInputKeyPressEventData
} from 'react-native';
import Markdown from 'react-native-markdown-display';
import MessageBubble from './components/MessageBubble';
import Message from './constants/Message';

// Get screen dimensions for responsive design
const { width } = Dimensions.get('window');
const MAX_BUBBLE_WIDTH = width * 0.75;

// Configure API endpoint based on platform
const API_BASE_URL = Platform.select({
  ios: 'http://localhost:2002', // iOS simulator can access localhost
  android: 'http://10.0.2.2:2002', // Android emulator uses 10.0.2.2 to access host's localhost
  web: 'http://127.0.0.1:2002', // Web uses standard localhost
  default: 'http://127.0.0.1:2002', // Fallback
});

export default function App() {
  const [prompt, setPrompt] = useState('');
  const [messages, setMessages] = useState<Message[]>([]);
  const [loading, setLoading] = useState(false);
  const scrollViewRef = useRef<ScrollView>(null);
  const [shiftPressed, setShiftPressed] = useState(false);
  const [apiError, setApiError] = useState<string | null>(null);

  useEffect(() => {
    fetchMessages();
  }, []);

  useEffect(() => {
    // Scroll to bottom whenever messages change
    if (scrollViewRef.current) {
      scrollViewRef.current.scrollToEnd({ animated: true });
    }
  }, [messages]);

  async function fetchMessages() {
    setApiError(null);
    try {
      const response = await fetch(`${API_BASE_URL}/chat/`);
      await handleFetchResponse(response);
    } catch (error) {
      console.error('Fetch error:', error);
      setApiError('Network connection failed. Please check your server.');
      setLoading(false);
    }
  }

  async function handleFetchResponse(response: Response) {
    let text = '';
    const decoder = new TextDecoder('utf-8');
    if (response.ok) {
      const reader = response.body?.getReader();
      if (!reader) return;
      try {
        while (true) {
          const { done, value } = await reader.read();
          if (done) break;
          text += decoder.decode(value);
          addMessages(text);
        }
        setLoading(false);
      } catch (error) {
        console.error('Stream reading error:', error);
        setApiError('Error reading response data');
        setLoading(false);
      }
    } else {
      console.error(`Server error: ${response.status}`);
      setApiError(`Server error: ${response.status}`);
      setLoading(false);
    }
  }

  function addMessages(responseText: string) {
    try {
      const lines = responseText.split('\n').filter(line => line.trim().length > 1);
      const newMessages = lines
        .map(line => {
          try {
        const parsedMessage = JSON.parse(line) as Message;
        return parsedMessage;
          } catch (error) {
        console.error('Failed to parse message line:', line, error);
        return null;
          }
        })
        .filter(message => message !== null);
      setMessages(prev => {
        const map = new Map(prev.map(m => [`${m.timestamp}-${m.role}`, m]));
        newMessages.forEach(msg => map.set(`${msg.timestamp}-${msg.role}`, msg));
        return Array.from(map.values());
      });
    } catch (error) {
      console.error('Error parsing messages:', error);
      setApiError('Invalid message format from server');
    }
  }

  async function onSubmit() {
    if (!prompt.trim()) return;
    
    setLoading(true);
    setApiError(null);
    try {
      const formData = new FormData();
      formData.append('prompt', prompt);

      setPrompt('');

      const response = await fetch(`${API_BASE_URL}/chat/`, {
        method: 'POST',
        body: formData,
      });

      await handleFetchResponse(response);
    } catch (error) {
      console.error('Submit error:', error);
      setApiError('Failed to send message. Network error.');
      setLoading(false);
    }
  }

  const handleKeyPress = (e: NativeSyntheticEvent<TextInputKeyPressEventData>) => {
    if (e.nativeEvent.key === 'Enter') {
      // Only check for shift on web platform
      if (Platform.OS === 'web' && shiftPressed) {
        return false; // Allow new line with Shift+Enter on web
      }
      
      // On native, Enter always submits
      // On web, Enter without shift submits
      e.preventDefault && e.preventDefault();
      onSubmit();
      return true;
    }
    return false;
  };

  const formatTimestamp = (timestamp: string) => {
    try {
      const date = new Date(timestamp);
      return date.toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' });
    } catch (e) {
      return '';
    }
  };

  // Group messages by date for iMessage-like date headers
  const getMessageGroups = () => {
    const groups: {date: string, messages: Message[]}[] = [];
    let currentDate = '';
    let currentGroup: Message[] = [];

    messages.forEach(msg => {
      const date = new Date(msg?.timestamp).toLocaleDateString();
      if (date !== currentDate) {
        if (currentGroup.length > 0) {
          groups.push({date: currentDate, messages: [...currentGroup]});
        }
        currentDate = date;
        currentGroup = [msg];
      } else {
        currentGroup.push(msg);
      }
    });

    if (currentGroup.length > 0) {
      groups.push({date: currentDate, messages: currentGroup});
    }

    return groups;
  };

  // Platform-specific key event handling
  useEffect(() => {
    // Only add event listeners if we're on web platform
    if (Platform.OS === 'web') {
      const handleKeyDown = (e: any) => {
        if (e.key === 'Shift') setShiftPressed(true);
      };
      
      const handleKeyUp = (e: any) => {
        if (e.key === 'Shift') setShiftPressed(false);
      };

      // Safe way to check if window exists and add event listeners
      const webWindow = typeof window !== 'undefined' ? window : null;
      if (webWindow) {
        webWindow.addEventListener('keydown', handleKeyDown);
        webWindow.addEventListener('keyup', handleKeyUp);
        
        // Clean up
        return () => {
          webWindow.removeEventListener('keydown', handleKeyDown);
          webWindow.removeEventListener('keyup', handleKeyUp);
        };
      }
    }
    
    // No cleanup needed for native platforms
    return () => {};
  }, []);
  
  return (
    <SafeAreaView style={styles.container}>
      <View style={styles.header}>
        <Text style={styles.headerTitle}>Messages</Text>
      </View>
      
      <KeyboardAvoidingView 
        style={styles.contentContainer} 
        behavior={Platform.OS === 'ios' ? 'padding' : undefined}
        keyboardVerticalOffset={Platform.OS === 'ios' ? 90 : 0}
      >
        <ScrollView
          ref={scrollViewRef}
          style={styles.messagesContainer}
          contentContainerStyle={styles.scrollContent}
        >
          {apiError && (
            <View style={styles.errorContainer}>
              <Text style={styles.errorText}>{apiError}</Text>
              <TouchableOpacity onPress={fetchMessages} style={styles.retryButton}>
                <Text style={styles.retryButtonText}>Retry</Text>
              </TouchableOpacity>
            </View>
          )}
          
          {getMessageGroups().map((group, groupIndex) => (
            <View key={`group-${groupIndex}`}>
              <View style={styles.dateHeaderContainer}>
                <Text style={styles.dateHeader}>{group.date}</Text>
              </View>
              
              {group.messages.map((msg, index) => {
                const isUserMessage = msg.role === 'user';
                const isConsecutive = index > 0 && group.messages[index - 1].role === msg.role;
                return (
                  <MessageBubble
                    key={`${msg.timestamp}-${msg.role}`}
                    msg={msg}
                    isUserMessage={isUserMessage}
                    isConsecutive={isConsecutive}
                    formatTimestamp={formatTimestamp}
                  />
                );
              })}
            </View>
          ))}
          
          {loading && (
            <View style={styles.loadingContainer}>
              <ActivityIndicator size="small" color="#0084ff" />
            </View>
          )}
        </ScrollView>
        
        <View style={styles.inputWrapper}>
          <View style={styles.inputContainer}>
            <TextInput
              style={styles.input}
              value={prompt}
              onChangeText={setPrompt}
              placeholder="iMessage"
              placeholderTextColor="#8E8E93"
              multiline
              onKeyPress={handleKeyPress}
              blurOnSubmit={false}
            />
            <TouchableOpacity 
              style={styles.sendButton} 
              onPress={onSubmit}
              disabled={!prompt.trim()}
            >
              <View style={[
                styles.sendButtonBackground,
                prompt.trim() ? styles.sendButtonActive : styles.sendButtonInactive
              ]}>
                <Text style={styles.sendButtonText}>↑</Text>
              </View>
            </TouchableOpacity>
          </View>
        </View>
      </KeyboardAvoidingView>
    </SafeAreaView>
  );
}

const styles = StyleSheet.create({
  container: { 
    flex: 1, 
    backgroundColor: '#FFFFFF' 
  },
  header: { 
    paddingVertical: 16, 
    borderBottomWidth: 1, 
    borderBottomColor: '#E9E9E9',
    backgroundColor: '#F9F9F9'
  },
  headerTitle: { 
    fontSize: 18, 
    fontWeight: 'bold', 
    textAlign: 'center',
    color: '#000000'
  },
  contentContainer: { flex: 1 },
  messagesContainer: { 
    flex: 1, 
    backgroundColor: '#FFFFFF' 
  },
  scrollContent: { 
    paddingHorizontal: 10,
    paddingBottom: 20,
    paddingTop: 10
  },
  dateHeaderContainer: { 
    alignItems: 'center', 
    marginVertical: 10 
  },
  dateHeader: { 
    fontSize: 12, 
    color: '#8E8E93',
    backgroundColor: 'rgba(0,0,0,0.05)',
    paddingVertical: 4,
    paddingHorizontal: 12,
    borderRadius: 10,
    overflow: 'hidden'
  },
  messageRow: { 
    flexDirection: 'row', 
    marginVertical: 2 
  },
  avatarContainer: { 
    justifyContent: 'flex-end', 
    alignItems: 'center', 
    marginRight: 8,
    paddingBottom: 15
  },
  avatar: { 
    backgroundColor: '#E1E1E1', 
    borderRadius: 15, 
    width: 30, 
    height: 30, 
    justifyContent: 'center', 
    alignItems: 'center' 
  },
  avatarText: { 
    color: '#888888', 
    fontSize: 12,
    fontWeight: 'bold' 
  },
  messageContainer: { 
    maxWidth: MAX_BUBBLE_WIDTH,
    marginVertical: 2
  },
  userMessageContainer: { 
    alignSelf: 'flex-end',
    marginLeft: 50
  },
  aiMessageContainer: { 
    alignSelf: 'flex-start',
    marginRight: 50
  },
  firstAiMessage: { 
    marginTop: 8 
  },
  consecutiveAiMessage: { 
    marginTop: 2 
  },
  messageBubble: { 
    padding: 12,
    borderRadius: 18,
    minHeight: 36
  },
  userBubble: { 
    backgroundColor: '#0B93F6',
    marginLeft: 40,
    borderTopRightRadius: 4
  },
  aiBubble: { 
    backgroundColor: '#E9E9EB',
    borderTopLeftRadius: 4
  },
  consecutiveBubble: { 
    marginTop: 2,
    borderTopLeftRadius: 18,
    borderTopRightRadius: 18
  },
  timestamp: { 
    fontSize: 10, 
    color: '#8E8E93', 
    paddingTop: 2,
    paddingHorizontal: 4
  },
  userTimestamp: { 
    alignSelf: 'flex-end'
  },
  aiTimestamp: { 
    alignSelf: 'flex-start'
  },
  loadingContainer: { 
    flexDirection: 'row', 
    justifyContent: 'center', 
    marginVertical: 10 
  },
  inputWrapper: { 
    borderTopWidth: 0.5, 
    borderTopColor: '#E9E9E9', 
    padding: 10,
    backgroundColor: '#FFFFFF'
  },
  inputContainer: { 
    flexDirection: 'row', 
    alignItems: 'flex-end'
  },
  input: { 
    flex: 1, 
    borderWidth: 1, 
    borderColor: '#DDDDDD', 
    borderRadius: 20, 
    paddingHorizontal: 16, 
    paddingVertical: 10,
    paddingRight: 40,
    minHeight: 40,
    maxHeight: 120,
    backgroundColor: '#FFFFFF',
    fontSize: 16
  },
  sendButton: { 
    position: 'absolute',
    right: 5,
    bottom: 5
  },
  sendButtonBackground: { 
    borderRadius: 15, 
    width: 30, 
    height: 30, 
    justifyContent: 'center', 
    alignItems: 'center' 
  },
  sendButtonActive: { 
    backgroundColor: '#0B93F6' 
  },
  sendButtonInactive: { 
    backgroundColor: '#E9E9EB' 
  },
  sendButtonText: { 
    color: '#FFFFFF', 
    fontWeight: 'bold', 
    fontSize: 16 
  },
  errorContainer: {
    backgroundColor: '#FFEBEE',
    padding: 12,
    borderRadius: 8,
    marginVertical: 10,
    marginHorizontal: 15,
    alignItems: 'center',
  },
  errorText: {
    color: '#D32F2F',
    fontSize: 14,
    marginBottom: 10,
    textAlign: 'center',
  },
  retryButton: {
    backgroundColor: '#0B93F6',
    paddingHorizontal: 16,
    paddingVertical: 8,
    borderRadius: 20,
  },
  retryButtonText: {
    color: '#FFFFFF',
    fontWeight: 'bold',
  },
});
