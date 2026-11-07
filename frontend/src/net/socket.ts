export function createVoiceSocket(wsUrl: string, token?: string): WebSocket {
  const url = new URL(wsUrl);
  const socket = new WebSocket(url);
  socket.binaryType = 'arraybuffer';
  socket.addEventListener('open', () => {
    socket.send(JSON.stringify({ type: 'auth', token: token || '' }));
  }, { once: true });
  return socket;
}
