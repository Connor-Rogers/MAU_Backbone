import React, { useRef } from 'react';
import {
  View,
  Text,
  TextInput,
  TouchableOpacity,
  ScrollView,
  StyleSheet,
  ActivityIndicator,
  NativeSyntheticEvent,
  TextInputKeyPressEventData
} from 'react-native';
import MessageBubble from './MessageBubble';
import Message from '../constants/Message';

// Props passed from App
export interface ChatPaneProps {
  messages: Message[];
  prompt: string;
  setPrompt: (text: string) => void;
  onSubmit: () => void;
  loading: boolean;
  apiError: string | null;
}

export default function ChatPane({ messages, prompt, setPrompt, onSubmit, loading, apiError }: ChatPaneProps) {
  const scrollRef = useRef<ScrollView>(null);
  // Scroll to bottom on new messages
  React.useEffect(() => {
    scrollRef.current?.scrollToEnd({ animated: true });
  }, [messages]);

  const formatTime = (ts: string) => new Date(ts).toLocaleTimeString([], { hour:'2-digit', minute:'2-digit' });
  const groups = messages.reduce((acc, m) => {
    const date = new Date(m.timestamp).toLocaleDateString();
    const grp = acc.find(g => g.date===date) || (acc.push({date, msgs: []}), acc[acc.length-1]);
    grp.msgs.push(m);
    return acc;
  }, [] as {date:string;msgs:Message[]}[]);

  return (
    <View style={styles.container}>
      {apiError && <Text style={styles.error}>{apiError}</Text>}
      <ScrollView ref={scrollRef} style={styles.list} contentContainerStyle={styles.content}>
        {groups.map((g,i) => (
          <View key={i}>
            <Text style={styles.date}>{g.date}</Text>
            {g.msgs.map((m,j) => (
              <MessageBubble
                key={`${m.timestamp}-${m.role}`}
                msg={m}
                isUserMessage={m.role==='user'}
                isConsecutive={j>0 && g.msgs[j-1].role===m.role}
                formatTimestamp={formatTime}
              />
            ))}
          </View>
        ))}
        {loading && <ActivityIndicator style={styles.loading} color="#FF4136" />}
      </ScrollView>
      <View style={styles.inputWrap}>
        <TextInput
          style={styles.input}
          value={prompt}
          onChangeText={setPrompt}
          placeholder="Enter command..."
          placeholderTextColor="#555"
          multiline
          onSubmitEditing={onSubmit}
          blurOnSubmit={false}
        />
        <TouchableOpacity onPress={onSubmit} disabled={!prompt.trim()} style={styles.sendBtn}>
          <Text style={[styles.sendTxt, prompt.trim()?styles.active:styles.inactive]}>➤</Text>
        </TouchableOpacity>
      </View>
    </View>
  );
}

const styles = StyleSheet.create({
  container: { flex:1, backgroundColor:'#121212' },
  list: { flex:1 },
  content: { padding:12, paddingBottom:20 },
  date: { textAlign:'center', color:'#888', backgroundColor:'rgba(255,255,255,0.1)', padding:4, borderRadius:6, marginVertical:10, fontSize:12 },
  loading: { marginVertical:10 },
  error: { color:'#FF4136', textAlign:'center', margin:8 },
  inputWrap: { flexDirection:'row', alignItems:'flex-end', padding:10, borderTopWidth:1, borderTopColor:'#333', backgroundColor:'#181818' },
  input: { flex:1, color:'#EEE', backgroundColor:'#1E1E1E', borderRadius:20, paddingHorizontal:16, paddingVertical:10, maxHeight:100, borderWidth:1, borderColor:'#333' },
  sendBtn: { marginLeft:8, padding:8 },
  sendTxt: { fontSize:20 },
  active: { color:'#2ECC40' },
  inactive: { color:'#555' }
});