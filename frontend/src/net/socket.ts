export function createVoiceSocket(wsUrl: string, token?: string): WebSocket {
  const url = new URL(wsUrl);
  if (token) url.searchParams.set('token', token);
  const socket = new WebSocket(url);
  socket.binaryType = 'arraybuffer';
  return socket;
}
