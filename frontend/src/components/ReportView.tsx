import { Check, ChevronDown, ChevronRight, Copy, FileBarChart } from "lucide-react";
import { useCallback, useState } from "react";
import { Streamdown } from "streamdown";
import "streamdown/styles.css";
import type { Citation } from "../types";
import { CitationBadge } from "./CitationBadge";
import { splitContentWithCitations } from "../lib/citations";

interface ReportSection {
	title: string;
	content: string;
}

function parseReportSections(content: string): ReportSection[] {
	const sections: ReportSection[] = [];
	const lines = content.split("\n");
	let currentTitle = "";
	let currentContent: string[] = [];

	for (const line of lines) {
		if (line.startsWith("## ")) {
			if (currentTitle) {
				sections.push({ title: currentTitle, content: currentContent.join("\n").trim() });
			}
			currentTitle = line.replace("## ", "").trim();
			currentContent = [];
		} else if (currentTitle) {
			currentContent.push(line);
		}
	}
	if (currentTitle) {
		sections.push({ title: currentTitle, content: currentContent.join("\n").trim() });
	}
	return sections;
}

interface CollapsibleSectionProps {
	title: string;
	content: string;
	citations: Citation[];
	defaultOpen?: boolean;
	onCitationClick: (documentId: string, pageNumber: number, clause?: string | null) => void;
}

function CollapsibleSection({
	title,
	content,
	citations,
	defaultOpen = false,
	onCitationClick,
}: CollapsibleSectionProps) {
	const [open, setOpen] = useState(defaultOpen);

	const segments = splitContentWithCitations(content, citations);
	const hasCitations = segments.some((s) => s.type === "citation");

	return (
		<div className="border border-neutral-200 rounded-lg overflow-hidden">
			<button
				type="button"
				onClick={() => setOpen(!open)}
				className="flex items-center gap-2 w-full px-3 py-2.5 text-left bg-neutral-50 hover:bg-neutral-100 transition-colors"
			>
				{open ? (
					<ChevronDown className="h-4 w-4 text-neutral-500 flex-shrink-0" />
				) : (
					<ChevronRight className="h-4 w-4 text-neutral-500 flex-shrink-0" />
				)}
				<span className="text-sm font-medium text-neutral-800">{title}</span>
			</button>
			{open && (
				<div className="px-4 py-3 prose prose-sm max-w-none">
					{hasCitations ? (
						<>
							{segments.map((segment, i) => {
								if (segment.type === "text" && segment.text) {
									return <Streamdown key={`text-${i}`}>{segment.text}</Streamdown>;
								}
								if (segment.type === "citation" && segment.citations) {
									return (
										<span key={`cite-group-${i}`} className="inline-flex flex-wrap gap-0.5">
											{segment.citations.map((c, j) => (
												<CitationBadge
													key={`cite-${i}-${j}`}
													citation={c.citation}
													marker={c.marker}
													onClick={onCitationClick}
												/>
											))}
										</span>
									);
								}
								return null;
							})}
						</>
					) : (
						<Streamdown>{content}</Streamdown>
					)}
				</div>
			)}
		</div>
	);
}

interface ReportViewProps {
	content: string;
	citations: Citation[];
	sourcesCited: number;
	onCitationClick: (documentId: string, pageNumber: number, clause?: string | null) => void;
}

export function ReportView({ content, citations, sourcesCited, onCitationClick }: ReportViewProps) {
	const sections = parseReportSections(content);
	const [copied, setCopied] = useState(false);

	const handleCopy = useCallback(() => {
		navigator.clipboard.writeText(content);
		setCopied(true);
		setTimeout(() => setCopied(false), 2000);
	}, [content]);

	return (
		<div className="space-y-2">
			<div className="flex items-center gap-2 mb-3">
				<FileBarChart className="h-4 w-4 text-neutral-700" />
				<span className="text-sm font-semibold text-neutral-800">Property Analysis Report</span>
				<span className="text-xs text-neutral-400">{sections.length} sections</span>
				{sourcesCited > 0 && (
					<span className="text-xs text-neutral-400">
						&bull; {sourcesCited} source{sourcesCited !== 1 ? "s" : ""}
					</span>
				)}
				<button
					type="button"
					onClick={handleCopy}
					className="ml-auto flex items-center gap-1 rounded-md border border-neutral-200 px-2 py-1 text-xs text-neutral-600 hover:bg-neutral-50 transition-colors"
					title="Copy report as Markdown"
				>
					{copied ? (
						<>
							<Check className="h-3 w-3 text-emerald-500" />
							<span className="text-emerald-600">Copied</span>
						</>
					) : (
						<>
							<Copy className="h-3 w-3" />
							<span>Copy Markdown</span>
						</>
					)}
				</button>
			</div>
			<div className="space-y-1.5">
				{sections.map((section, i) => (
					<CollapsibleSection
						key={section.title}
						title={section.title}
						content={section.content}
						citations={citations}
						defaultOpen={i === 0}
						onCitationClick={onCitationClick}
					/>
				))}
			</div>
		</div>
	);
}

export function isReportMessage(content: string): boolean {
	const headerCount = (content.match(/^## /gm) || []).length;
	return headerCount >= 3;
}
