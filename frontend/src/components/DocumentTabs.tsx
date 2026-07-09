import { FileText } from "lucide-react";
import type { Document } from "../types";

interface DocumentTabsProps {
	documents: Document[];
	activeDocumentId: string | null;
	onSelect: (docId: string) => void;
}

export function DocumentTabs({
	documents,
	activeDocumentId,
	onSelect,
}: DocumentTabsProps) {
	if (documents.length === 0) return null;

	return (
		<div className="flex items-center gap-1 overflow-x-auto border-b border-neutral-100 px-3 py-2">
			{documents.map((doc) => {
				const isActive = doc.id === activeDocumentId;
				const displayName = doc.filename.replace(".pdf", "").replace(".PDF", "");
				const truncated =
					displayName.length > 18
						? `${displayName.slice(0, 16)}...`
						: displayName;

				return (
					<button
						key={doc.id}
						type="button"
						onClick={() => onSelect(doc.id)}
						className={`flex items-center gap-1.5 rounded-md px-2.5 py-1.5 text-xs font-medium whitespace-nowrap transition-colors ${
							isActive
								? "bg-neutral-900 text-white"
								: "bg-neutral-100 text-neutral-600 hover:bg-neutral-200"
						}`}
						title={doc.filename}
					>
						<FileText className="h-3 w-3 flex-shrink-0" />
						{truncated}
						<span
							className={`text-[10px] ${isActive ? "text-neutral-300" : "text-neutral-400"}`}
						>
							{doc.page_count}p
						</span>
					</button>
				);
			})}
		</div>
	);
}
