interface ModulePlaceholderProps {
  moduleNumber: string;
  title: string;
  description: string;
  plannedPhase: string;
}

export function ModulePlaceholder({
  moduleNumber,
  title,
  description,
  plannedPhase,
}: ModulePlaceholderProps) {
  return (
    <section className="mx-auto max-w-4xl rounded-md border border-[#E4E9E6] bg-white p-6">
      <div className="flex items-center justify-between border-b border-[#E4E9E6] pb-4">
        <div>
          <span className="font-mono text-xs font-semibold uppercase tracking-wider text-[#246B60]">
            Module {moduleNumber}
          </span>
          <h2 className="mt-1 text-xl font-semibold text-[#122D33]">{title}</h2>
        </div>
        <span className="rounded border border-[#E4E9E6] bg-[#F6F7F4] px-2.5 py-1 font-mono text-xs text-[#68777C]">
          {plannedPhase}
        </span>
      </div>
      <p className="mt-4 text-sm leading-relaxed text-[#68777C]">{description}</p>
      <p className="mt-3 text-xs text-[#68777C]">
        Backend API endpoints are active under <code className="font-mono text-[#122D33]">/api/v1</code>;
        the dedicated deep-dive view for this module is scheduled for the next UI phase.
      </p>
    </section>
  );
}
