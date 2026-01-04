"use client";
import { useEffect, useState } from 'react';
import dynamic from 'next/dynamic';
import Titantron from '@/components/Titantron';
import DiscoveryConsole from '@/components/DiscoveryConsole';
import { useStore } from '@/lib/store';
import { Dna, Activity, Terminal, ShieldCheck } from 'lucide-react';

const ForceGraphView = dynamic(() => import('@/components/ForceGraphView'), { ssr: false });

export default function Home() {
  const { isFlyByActive, toggleFlyBy } = useStore();
  const [logs, setLogs] = useState<string[]>(["SYSTEM READY", "WAITING FOR NODE SELECTION..."]);
  const [mounted, setMounted] = useState(false);

  useEffect(() => { setMounted(true); }, []);
  const addLog = (msg: string) => setLogs(prev => [msg, ...prev].slice(0, 5));

  return (
    <main className="h-screen w-screen bg-white flex flex-col overflow-hidden font-sans text-slate-900">
      <nav className="h-14 border-b border-slate-200 flex items-center px-6 justify-between shrink-0 bg-white z-50">
        <div className="flex items-center gap-2">
            <div className="p-1.5 bg-red-600 rounded-lg shadow-lg shadow-red-200"><Dna className="text-white w-4 h-4" /></div>
            <h1 className="text-lg font-black tracking-tighter uppercase">Helix<span className="text-red-600 italic">Stream</span></h1>
        </div>
        <div className="flex items-center gap-4">
            <div className="px-3 py-1 bg-slate-50 border border-slate-200 rounded text-[10px] font-mono text-slate-500 flex items-center gap-2">
                <ShieldCheck className="w-3 h-3 text-green-500" />
                PIPELINE: HYBRID_FAILOVER
            </div>
            <button onClick={toggleFlyBy} className={`text-[10px] font-bold px-3 py-1 rounded border transition-all ${isFlyByActive ? 'bg-red-600 text-white border-red-600 shadow-md' : 'bg-white text-slate-600 border-slate-200'}`}>
                {isFlyByActive ? 'ORBIT ACTIVE' : 'ENABLE FLY-BY'}
            </button>
        </div>
      </nav>

      <div className="flex-1 grid grid-cols-[1fr_450px] overflow-hidden">
        <section className="relative bg-slate-50 overflow-hidden">
          <ForceGraphView />
          <div className="absolute bottom-6 left-0 right-0 z-40 flex justify-center px-6">
             <DiscoveryConsole onLog={addLog} />
          </div>
        </section>

        <aside className="h-full flex flex-col border-l border-slate-200 bg-white overflow-hidden z-50 shadow-[-10px_0_20px_rgba(0,0,0,0.02)]">
            <div className="flex-1 overflow-hidden"><Titantron onLog={addLog} /></div>
            <div className="h-32 border-t border-slate-200 bg-slate-900 p-4 font-mono text-[10px] shrink-0">
                <div className="flex items-center gap-2 text-slate-500 mb-2 border-b border-slate-800 pb-1">
                    <Terminal className="w-3 h-3 text-red-600" />
                    <span className="font-bold tracking-widest">GATEWAY_DAEMON_FEED</span>
                </div>
                <div className="space-y-1 overflow-y-auto h-16 text-slate-400">
                    {mounted && logs.map((log, i) => (
                        <div key={i} className="flex gap-2">
                            <span className="text-red-900 font-bold">{'>'}</span>
                            <span className={i === 0 ? "text-slate-100" : ""}>{log}</span>
                        </div>
                    ))}
                </div>
            </div>
        </aside>
      </div>
    </main>
  );
}