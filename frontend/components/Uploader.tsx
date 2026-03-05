"use client";
import { useCallback, useState } from "react";
import { useRouter } from "next/navigation";

const API = process.env.NEXT_PUBLIC_API_URL;
const MAX_MB = 500;

export default function Uploader() {
  const [dragging, setDragging] = useState(false);
  const [uploading, setUploading] = useState(false);
  const [error, setError] = useState("");
  const router = useRouter();

  const handleFile = useCallback(
    async (file: File) => {
      if (uploading) return;
      if (!file.type.startsWith("video/")) {
        setError("Please upload a video file (mp4, mov, mkv).");
        return;
      }
      if (file.size > MAX_MB * 1024 * 1024) {
        setError(`File must be under ${MAX_MB}MB.`);
        return;
      }
      setError("");
      setUploading(true);
      const form = new FormData();
      form.append("file", file);
      try {
        const res = await fetch(`${API}/upload`, { method: "POST", body: form });
        if (!res.ok) {
          const body = await res.json().catch(() => ({}));
          throw new Error(body.detail || "Upload failed");
        }
        const { job_id } = await res.json();
        router.push(`/status/${job_id}`);
      } catch (e: unknown) {
        setError(e instanceof Error ? e.message : "Upload failed");
        setUploading(false);
      }
    },
    [router, uploading]
  );

  const onDrop = (e: React.DragEvent) => {
    e.preventDefault();
    setDragging(false);
    const file = e.dataTransfer.files[0];
    if (file) handleFile(file);
  };

  return (
    <div className="min-h-screen bg-gray-950 flex items-center justify-center p-6">
      <div className="max-w-xl w-full text-center space-y-6">
        <h1 className="text-4xl font-bold text-white tracking-tight">clipforge</h1>
        <p className="text-gray-400">
          Upload gameplay footage. Get TikTok, YouTube, and trailer clips — automatically.
        </p>

        <label
          className={`block border-2 border-dashed rounded-2xl p-16 cursor-pointer transition-colors ${
            dragging
              ? "border-violet-400 bg-violet-950/30"
              : "border-gray-700 hover:border-gray-500"
          }`}
          onDragOver={(e) => {
            e.preventDefault();
            setDragging(true);
          }}
          onDragLeave={() => setDragging(false)}
          onDrop={onDrop}
        >
          <input
            type="file"
            accept="video/*"
            className="hidden"
            onChange={(e) => {
              const f = e.target.files?.[0];
              if (f) handleFile(f);
            }}
          />
          <div className="space-y-3">
            <div className="text-5xl select-none">🎮</div>
            <p className="text-gray-300 text-lg">
              {uploading ? "Uploading…" : "Drop your gameplay video here"}
            </p>
            <p className="text-gray-500 text-sm">mp4 · mov · mkv · max 500 MB · max 10 min</p>
          </div>
        </label>

        {error && <p className="text-red-400 text-sm">{error}</p>}
      </div>
    </div>
  );
}
