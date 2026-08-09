/**
 * RUDRA AI - System Monitor Page
 * Live hardware analytics for CPU, RAM, Disk, Battery, Network, and Process Management.
 */

import { useEffect, useState } from 'react';
import { motion } from 'framer-motion';
import { Cpu, HardDrive, Zap, Activity, RefreshCw, Radio } from 'lucide-react';
import { useAppStore } from '../stores/appStore';
import { api, type SystemStats } from '../services/api';

export default function SystemMonitorPage() {
  const { systemStats, loadSystemStats } = useAppStore();
  const [liveStats, setLiveStats] = useState<SystemStats | null>(systemStats);
  const [isConnected, setIsConnected] = useState(false);

  useEffect(() => {
    loadSystemStats();

    let ws: WebSocket | null = null;
    try {
      ws = api.connectSystemStream((data) => {
        setLiveStats(data);
        setIsConnected(true);
      });

      ws.onclose = () => setIsConnected(false);
      ws.onerror = () => setIsConnected(false);
    } catch {
      setIsConnected(false);
    }

    return () => {
      if (ws) ws.close();
    };
  }, []);

  const stats = liveStats || systemStats;

  if (!stats) {
    return (
      <div className="page-container" style={{ display: 'flex', alignItems: 'center', justifyContent: 'center' }}>
        <div style={{ textAlign: 'center', color: 'var(--text-secondary)' }}>
          <RefreshCw size={32} className="spin" style={{ marginBottom: 12, color: 'var(--accent-primary)' }} />
          <div>Connecting to System Monitor Service...</div>
        </div>
      </div>
    );
  }

  const getProgressColorClass = (percent: number) => {
    if (percent > 85) return 'danger';
    if (percent > 70) return 'warning';
    return '';
  };

  return (
    <div className="page-container" id="system-monitor-page">
      <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'flex-start', marginBottom: 20 }}>
        <div>
          <h1 className="page-title">System Performance Monitor</h1>
          <p className="page-subtitle">Real-time CPU, RAM, Storage, Network and Active Process Diagnostics</p>
        </div>
        <div style={{ display: 'flex', alignItems: 'center', gap: 8, fontSize: 12, color: isConnected ? 'var(--success)' : 'var(--warning)' }}>
          <Radio size={14} className={isConnected ? 'pulse' : ''} />
          {isConnected ? 'Live WebSocket Active' : 'Polling Mode'}
        </div>
      </div>

      {/* KPI Cards */}
      <div className="stats-grid">
        {/* CPU */}
        <motion.div className="stat-card" initial={{ opacity: 0, y: 15 }} animate={{ opacity: 1, y: 0 }} transition={{ delay: 0.1 }}>
          <div className="stat-header">
            <span className="stat-label">CPU Load</span>
            <Cpu size={18} className="stat-icon" />
          </div>
          <div className="stat-value">
            {stats.cpu.percent}%
          </div>
          <div className="stat-detail">
            {stats.cpu.count} Logical Cores • {stats.cpu.frequency_mhz ? `${stats.cpu.frequency_mhz} MHz` : 'Intel i3 10th Gen'}
          </div>
          <div className="progress-bar">
            <div className={`progress-fill ${getProgressColorClass(stats.cpu.percent)}`} style={{ width: `${stats.cpu.percent}%` }} />
          </div>
        </motion.div>

        {/* RAM */}
        <motion.div className="stat-card" initial={{ opacity: 0, y: 15 }} animate={{ opacity: 1, y: 0 }} transition={{ delay: 0.2 }}>
          <div className="stat-header">
            <span className="stat-label">RAM Usage</span>
            <Activity size={18} className="stat-icon" />
          </div>
          <div className="stat-value">
            {stats.memory.used_gb} <span className="stat-unit">/ {stats.memory.total_gb} GB</span>
          </div>
          <div className="stat-detail">
            {stats.memory.available_gb} GB Available ({stats.memory.percent}% used)
          </div>
          <div className="progress-bar">
            <div className={`progress-fill ${getProgressColorClass(stats.memory.percent)}`} style={{ width: `${stats.memory.percent}%` }} />
          </div>
        </motion.div>

        {/* Storage */}
        <motion.div className="stat-card" initial={{ opacity: 0, y: 15 }} animate={{ opacity: 1, y: 0 }} transition={{ delay: 0.3 }}>
          <div className="stat-header">
            <span className="stat-label">Disk Storage (C:)</span>
            <HardDrive size={18} className="stat-icon" />
          </div>
          <div className="stat-value">
            {stats.disk.used_gb} <span className="stat-unit">/ {stats.disk.total_gb} GB</span>
          </div>
          <div className="stat-detail">
            {stats.disk.free_gb} GB Free ({stats.disk.percent}% occupied)
          </div>
          <div className="progress-bar">
            <div className={`progress-fill ${getProgressColorClass(stats.disk.percent)}`} style={{ width: `${stats.disk.percent}%` }} />
          </div>
        </motion.div>

        {/* Battery / System Uptime */}
        <motion.div className="stat-card" initial={{ opacity: 0, y: 15 }} animate={{ opacity: 1, y: 0 }} transition={{ delay: 0.4 }}>
          <div className="stat-header">
            <span className="stat-label">{stats.battery ? 'Power Status' : 'System Uptime'}</span>
            <Zap size={18} className="stat-icon" />
          </div>
          <div className="stat-value">
            {stats.battery ? `${stats.battery.percent}%` : `${stats.uptime_hours} hrs`}
          </div>
          <div className="stat-detail">
            {stats.battery
              ? `${stats.battery.plugged ? 'AC Plugged In' : 'On Battery'} ${stats.battery.time_left ? `(${stats.battery.time_left} left)` : ''}`
              : `System running continuously for ${stats.uptime_hours} hours`}
          </div>
          {stats.battery?.percent && (
            <div className="progress-bar">
              <div className="progress-fill" style={{ width: `${stats.battery.percent}%`, background: 'var(--success)' }} />
            </div>
          )}
        </motion.div>
      </div>

      {/* Process Manager Section */}
      <motion.div className="card" initial={{ opacity: 0, y: 20 }} animate={{ opacity: 1, y: 0 }} transition={{ delay: 0.5 }}>
        <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: 16 }}>
          <div>
            <h3 className="card-title">Top Active Processes</h3>
            <p className="card-subtitle">Monitored processes sorted by current CPU consumption</p>
          </div>
          <span style={{ fontSize: 11, color: 'var(--text-tertiary)' }}>Auto-refreshed live</span>
        </div>

        <div style={{ overflowX: 'auto' }}>
          <table className="process-table">
            <thead>
              <tr>
                <th>PID</th>
                <th>Process Name</th>
                <th>CPU %</th>
                <th>Memory %</th>
                <th>Status</th>
              </tr>
            </thead>
            <tbody>
              {stats.top_processes.map((proc) => (
                <tr key={proc.pid}>
                  <td style={{ fontFamily: 'var(--font-mono)', fontSize: 12 }}>{proc.pid}</td>
                  <td style={{ fontWeight: 500, color: 'var(--text-primary)' }}>{proc.name}</td>
                  <td style={{ fontWeight: 600, color: proc.cpu_percent > 20 ? 'var(--warning)' : 'inherit' }}>
                    {proc.cpu_percent.toFixed(1)}%
                  </td>
                  <td>{proc.memory_percent.toFixed(1)}%</td>
                  <td>
                    <span style={{
                      padding: '2px 8px',
                      borderRadius: 12,
                      fontSize: 10,
                      fontWeight: 600,
                      background: proc.status === 'running' ? 'rgba(34, 197, 94, 0.15)' : 'rgba(255, 255, 255, 0.05)',
                      color: proc.status === 'running' ? 'var(--success)' : 'var(--text-tertiary)',
                    }}>
                      {proc.status}
                    </span>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </motion.div>
    </div>
  );
}
