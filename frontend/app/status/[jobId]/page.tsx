import StatusPoller from "@/components/StatusPoller";

export default function StatusPage({
  params,
}: {
  params: { jobId: string };
}) {
  return (
    <div className="min-h-screen bg-gray-950 flex items-center justify-center p-6">
      <StatusPoller jobId={params.jobId} />
    </div>
  );
}
