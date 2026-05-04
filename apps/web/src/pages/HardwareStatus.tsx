import { useState, useEffect } from "react";
import {
  Cpu,
  HardDrive,
  MemoryStick,
  Wifi,
  WifiOff,
  RefreshCw,
  Server,
  Gauge,
} from "lucide-react";
import StateWrapper from "@/components/ui/StateWrapper";
import type { ViewState } from "@/lib/types";

type DeviceInfo = {
  id: string;
  name: string;
  type: string;
  memory_gb: number;
  utilization_pct: number;
};

type HWPayload = {
  devices: DeviceInfo[];
  system_ram_gb: number;
  recommended_tier: string;
};

export default function HardwareStatus() {
  const [status, setStatus] = useState<HWPayload | null>(null);
  const [offline, setOffline] = useState(false);
  const [loading, setLoading] = useState(true);

  const fetchHW = () => {
    setLoading(true);
    fetch("http://127.0.0.1:4133/system/hardware")
      .then((res) => res.json())
      .then((data: HWPayload) => {
        setStatus(data);
        setOffline(false);
      })
      .catch(() => {
        setOffline(true);
        setStatus(null);
      })
      .finally(() => setLoading(false));
  };

  useEffect(() => {
    fetchHW();
  }, []);

  const viewState: ViewState =
    loading ? "loading" :
    !status ? "empty" :
    "success";

  return (
    <StateWrapper
      state={viewState}
      moduleName="Hardware Status"
      emptyTitle="Local Agent Not Reachable"
      emptyDescription="The Drug Designer Local Runtime Agent is not running on port 4133. Install and start the companion app for live hardware telemetry."
      errorInfo={offline ? { code: 'AGENT_OFFLINE', message: 'Local Agent not reachable on port 4133.' } : undefined}
      onRetry={fetchHW}
    >
    <div
      className="flex-1 overflow-y-auto"
      style={{ background: "var(--bg-app)" }}
    >
      <div className="max-w-[1100px] mx-auto px-6 py-5">
        <div className="mb-6 flex justify-between items-center">
          <div>
            <h1 className="text-lg font-semibold text-[var(--text-primary)]">
              Hardware Status
            </h1>
            <p className="text-xs text-[var(--text-muted)] mt-0.5">
              Live PCIe telemetry from the Local Runtime Agent via nvidia-smi &
              psutil.
            </p>
          </div>
          <button
            onClick={fetchHW}
            disabled={loading}
            className="glass-button flex items-center gap-2 px-4 py-2 text-sm"
          >
            <RefreshCw size={14} className={loading ? "animate-spin" : ""} />{" "}
            Rescan
          </button>
        </div>

        {offline ? (
          <div className="card p-12 flex flex-col items-center justify-center text-center">
            <WifiOff size={50} className="text-red-500/50 mb-4" />
            <h2 className="text-sm font-semibold text-[var(--text-primary)] mb-2">
              Local Agent Not Reachable
            </h2>
            <p className="text-xs text-[var(--text-muted)] max-w-sm mb-4">
              The Drug Designer Local Runtime Agent is either not running or not
              installed. Hardware telemetry requires the companion app on port
              4133.
            </p>
          </div>
        ) : status ? (
          <>
            <div className="grid grid-cols-1 md:grid-cols-3 gap-6 mb-6">
              <div className="card p-5 border-t-[3px] border-t-blue-500 text-center">
                <MemoryStick size={32} className="mx-auto text-blue-400 mb-3" />
                <h3 className="text-xs text-[var(--text-muted)] font-mono mb-1">
                  System RAM
                </h3>
                <div className="text-2xl font-bold text-[var(--text-primary)]">
                  {status.system_ram_gb} GB
                </div>
              </div>
              <div className="card p-5 border-t-[3px] border-t-purple-500 text-center">
                <Gauge size={32} className="mx-auto text-purple-400 mb-3" />
                <h3 className="text-xs text-[var(--text-muted)] font-mono mb-1">
                  Recommended Tier
                </h3>
                <div className="text-lg font-bold text-[var(--accent)] font-mono">
                  {status.recommended_tier}
                </div>
              </div>
              <div className="card p-5 border-t-[3px] border-t-green-500 text-center">
                <Wifi size={32} className="mx-auto text-green-400 mb-3" />
                <h3 className="text-xs text-[var(--text-muted)] font-mono mb-1">
                  Agent Status
                </h3>
                <div className="text-lg font-bold text-green-400">Online</div>
              </div>
            </div>

            <div className="card overflow-hidden">
              <div className="px-5 py-4 border-b border-border flex items-center gap-2">
                <Server size={16} className="text-[var(--accent)]" />
                <h2 className="text-sm font-semibold text-[var(--text-primary)]">
                  Detected Compute Devices
                </h2>
              </div>
              <table className="w-full text-left text-xs">
                <thead>
                  <tr className="border-b border-border bg-surface/50">
                    <th className="px-5 py-3 font-medium text-[var(--text-muted)]">
                      Device ID
                    </th>
                    <th className="px-5 py-3 font-medium text-[var(--text-muted)]">
                      Name
                    </th>
                    <th className="px-5 py-3 font-medium text-[var(--text-muted)]">
                      Type
                    </th>
                    <th className="px-5 py-3 font-medium text-[var(--text-muted)] text-right">
                      Memory
                    </th>
                  </tr>
                </thead>
                <tbody>
                  {status.devices.map((d, i) => (
                    <tr
                      key={i}
                      className="border-b border-border/50 hover:bg-surface/30 transition-colors"
                    >
                      <td className="px-5 py-3 font-mono text-amber-500">
                        {d.id}
                      </td>
                      <td className="px-5 py-3 text-[var(--text-primary)] font-medium">
                        {d.name}
                      </td>
                      <td className="px-5 py-3">
                        <span
                          className={`px-2 py-0.5 rounded text-[10px] font-mono ${d.type === "gpu" ? "bg-green-500/15 text-green-400" : "bg-blue-500/15 text-blue-400"}`}
                        >
                          {d.type.toUpperCase()}
                        </span>
                      </td>
                      <td className="px-5 py-3 text-right font-mono text-[var(--text-primary)]">
                        {d.memory_gb} GB
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          </>
        ) : (
          <div className="text-center text-xs text-[var(--text-muted)] mt-12 animate-pulse">
            Scanning system parameters...
          </div>
        )}
      </div>
    </div>
    </StateWrapper>
  );
}
