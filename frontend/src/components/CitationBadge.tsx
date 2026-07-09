import { FileText } from "lucide-react";
import type { Citation } from "../types";
import type { CitationMatch } from "../lib/citations";

interface CitationBadgeProps {
	citation?: Citation;
	marker: CitationMatch;
	onClick: (documentId: string, pageNumber: number, clause?: string | null) => void;
}

export function CitationBadge({ citation, marker, onClick }: CitationBadgeProps) {
	const docName = citation?.document_name ?? marker.documentName;
	const page = citation?.page_number ?? marker.pageNumber;
	const clause = citation?.clause ?? marker.clause;

	const colorClass = "bg-emerald-50 text-emerald-700 hover:bg-emerald-100 border-emerald-200";

	// Truncate long document names
	const displayName = docName.length > 20 ? `${docName.slice(0, 18)}...` : docName;

	return (
		<button
			type="button"
			onClick={() => {
			const docId = citation?.document_id;
			if (docId) onClick(docId, page, clause);
		}}
			className={`inline-flex items-center gap-0.5 rounded border px-1.5 py-0.5 text-xs font-medium transition-colors ${colorClass}`}
			title={`${docName} | Page ${page}${clause ? `, ${clause}` : ""}`}
		>
			<FileText className="h-3 w-3 flex-shrink-0" />
			<span className="truncate max-w-[120px]">{displayName}</span>
			<span className="text-[10px] opacity-75">p.{page}</span>
			{clause && <span className="text-[10px] opacity-75">{clause}</span>}
		</button>
	);
}
