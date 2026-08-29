import { useEffect } from "react";
import { io, type Socket } from "socket.io-client";
import { API_BASE, SESSION_KEYS } from "./api";

let socket: Socket | null = null;
let socketIdentity = "";

function activeBoothCredentials() {
  if (typeof window === "undefined") return null;
  const session_token = localStorage.getItem(SESSION_KEYS.token);
  const booth_id = localStorage.getItem(SESSION_KEYS.booth);
  return session_token && booth_id ? { session_token, booth_id } : null;
}

export function getSocket(): Socket {
  if (typeof window === "undefined") {
    // SSR guard — return a no-op stub
    return { on: () => {}, off: () => {}, emit: () => {} } as unknown as Socket;
  }
  const credentials = activeBoothCredentials();
  const nextIdentity = credentials ? `${credentials.booth_id}:${credentials.session_token}` : "";
  if (!socket) {
    socket = io(API_BASE, {
      transports: ["websocket", "polling"],
      autoConnect: false,
      reconnection: true,
      auth: credentials ?? {},
    });
    socketIdentity = nextIdentity;
  } else if (socketIdentity !== nextIdentity) {
    socket.disconnect();
    socket.auth = credentials ?? {};
    socketIdentity = nextIdentity;
  }

  if (credentials && !socket.connected) {
    socket.connect();
  }
  return socket;
}

export function useSocketEvent<T = unknown>(
  event: string,
  handler: (payload: T) => void,
) {
  useEffect(() => {
    const s = getSocket();
    const fn = (p: T) => handler(p);
    s.on(event, fn);
    return () => {
      s.off(event, fn);
    };
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [event]);
}
