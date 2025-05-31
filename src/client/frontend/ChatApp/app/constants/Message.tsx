export default interface Message {
  role: string;
  content: string;
  timestamp: string;
  view?: string | null;
}