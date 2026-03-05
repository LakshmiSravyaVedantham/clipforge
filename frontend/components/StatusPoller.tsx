"use client";
import { useEffect, useState } from "react";

const API = process.env.NEXT_PUBLIC_API_URL;

interface StatusData {
  job_id: string;
  status: "queued" | "processing" | "done" | "failed";
  progress: number;
  stage: string;
  error?: string;
}

export default function StatusPoller({ jobId }: { jobId: string }) {
  const [data, setData] = useState<StatusData | null>(null);

  useEffect(() => {
    let cancelled = false;
    const poll = async () => {
      try {
        const res = await fetch(`${API}/status/${jobId}`);
        if (!res.ok) {
          if (!cancelled) {
            setData({
              job_id: jobId,
              status: "failed",
              progress: 0,
              stage: "failed",
              error: `Server error: ${res.status}`,
            });
          }
          return;
        }
        const json: StatusData = await res.json();
        if (!cancelled) {
          setData(json);
          if (json.status !== "done" && json.status !== "failed") {
            setTimeout(poll, 2000);
          }
        }
      } catch {
        if (!cancelled) setTimeout(poll, 3000);
      }
    };
    poll();
    return () => { cancelled = true; };
  }, [jobId]);

  if (!data) {
    return <p className="text-gray-400 animate-pulse">Connecting…</p>;
  }

  if (data.status === "failed") {
    return (
      <div className="text-center space-y-4">
        <p className="text-red-400 text-xl font-semibold">Processing failed</p>
        {data.error && <p className="text-gray-500 text-sm">{data.error}</p>}
        <a href="/" className="text-violet-400 underline hover:text-violet-300">
          Try another video
        </a>
      </div>
    );
  }

  if (data.status === "done") {
    return (
      <div className="text-center space-y-6">
        <div className="text-5xl">✅</div>
        <h2 className="text-2xl font-bold text-white">Your clips are ready</h2>
        <a
          href={`${API}/download/${jobId}`}
          className="inline-block bg-violet-600 hover:bg-violet-500 text-white font-semibold px-8 py-4 rounded-xl text-lg transition-colors"
        >
          Download ZIP (TikTok + YouTube + Trailer)
        </a>
        <p className="text-gray-500 text-sm">Files available for 1 hour</p>
        <a href="/" className="block text-gray-500 hover:text-gray-300 text-sm transition-colors">
          Process another video
        </a>
      </div>
    );
  }

  return (
    <div className="text-center space-y-6 w-full max-w-sm">
      <div className="text-4xl animate-spin">⚙️</div>
      <p className="text-gray-300 capitalize">{data.stage.replace(/_/g, " ")}…</p>
      <div className="w-full bg-gray-800 rounded-full h-3 overflow-hidden">
        <div
          className="bg-violet-600 h-3 rounded-full transition-all duration-500"
          style={{ width: `${data.progress}%` }}
        />
      </div>
      <p className="text-gray-500 text-sm">{data.progress}%</p>
    </div>
  );
}
