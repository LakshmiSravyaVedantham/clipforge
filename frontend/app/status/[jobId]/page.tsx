import StatusPoller from "@/components/StatusPoller";

export default async function StatusPage({
  params,
}: {
  params: Promise<{ jobId: string }>;
}) {
  const { jobId } = await params;
  return (
    <div className="min-h-screen bg-gray-950 flex items-center justify-center p-6">
      <StatusPoller jobId={jobId} />
    </div>
  );
}
