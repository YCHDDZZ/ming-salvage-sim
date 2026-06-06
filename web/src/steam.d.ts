export {};

type SteamStatus = {
  ok: boolean;
  available: boolean;
  appId?: number | null;
  steamId64?: string;
  personaName?: string;
  error?: string;
};

type SteamResult = {
  ok: boolean;
  available: boolean;
  name?: string;
  previous?: number;
  value?: number;
  error?: string;
};

type SteamAuthTicket = SteamStatus & {
  identity?: string;
  ticket?: string;
  ticketId?: string;
  expiresInSeconds?: number;
};

type SteamServerAuthOptions = {
  url?: string;
  identity?: string;
  payload?: Record<string, unknown>;
  headers?: Record<string, string>;
};

type SteamServerAuthResult = SteamStatus & {
  identity?: string;
  status?: number;
  data?: unknown;
};

type LauncherLogInfo = {
  data_dir: string;
  log_path: string;
  exists: boolean;
  content: string;
};

declare global {
  interface ImportMeta {
    env: {
      VITE_API_BASE?: string;
    };
  }

  interface Window {
    pywebview?: {
      api?: {
        get_launcher_log?: () => Promise<LauncherLogInfo>;
        open_data_dir?: () => Promise<{ ok: boolean; data_dir: string }>;
      };
    };
    steam?: {
      getStatus: () => Promise<SteamStatus>;
      getAuthTicket: (identity?: string) => Promise<SteamAuthTicket>;
      cancelAuthTicket: (ticketId: string) => Promise<SteamResult>;
      authenticateWithServer: (options?: SteamServerAuthOptions) => Promise<SteamServerAuthResult>;
      addStatInt: (name: string, delta: number) => Promise<SteamResult>;
      setStatInt: (name: string, value: number) => Promise<SteamResult>;
      flushStats: () => Promise<SteamResult>;
    };
  }
}
