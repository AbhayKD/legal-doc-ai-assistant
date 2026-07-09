import { ChevronLeft, ChevronRight, FileText, Loader2 } from "lucide-react";
import { useCallback, useEffect, useMemo, useRef, useState } from "react";
import { Document as PDFDocument, Page, pdfjs } from "react-pdf";
import "react-pdf/dist/Page/AnnotationLayer.css";
import "react-pdf/dist/Page/TextLayer.css";
import { getDocumentUrl } from "../lib/api";
import type { Document } from "../types";
import { Button } from "./ui/button";
import { DocumentTabs } from "./DocumentTabs";

pdfjs.GlobalWorkerOptions.workerSrc = new URL(
	"pdfjs-dist/build/pdf.worker.min.mjs",
	import.meta.url,
).toString();

const MIN_WIDTH = 280;
const MAX_WIDTH = 700;
const DEFAULT_WIDTH = 420;

interface DocumentViewerProps {
	documents: Document[];
	activeDocumentId: string | null;
	activePage: number;
	highlightClause: string | null;
	citationActive: boolean;
	onDocumentSelect: (docId: string) => void;
	onPageChange: (page: number) => void;
}

export function DocumentViewer({
	documents,
	activeDocumentId,
	activePage,
	highlightClause,
	citationActive,
	onDocumentSelect,
	onPageChange,
}: DocumentViewerProps) {
	const [numPages, setNumPages] = useState<number>(0);
	const [pdfLoading, setPdfLoading] = useState(true);
	const [pdfError, setPdfError] = useState<string | null>(null);
	const [width, setWidth] = useState(DEFAULT_WIDTH);
	const [dragging, setDragging] = useState(false);
	const containerRef = useRef<HTMLDivElement>(null);

	const activeDocument = documents.find((d) => d.id === activeDocumentId) ?? null;

	// Reset PDF state when active document changes
	useEffect(() => {
		setPdfLoading(true);
		setPdfError(null);
		setNumPages(0);
	}, [activeDocumentId]);

	const handleMouseDown = useCallback(
		(e: React.MouseEvent) => {
			e.preventDefault();
			setDragging(true);

			const startX = e.clientX;
			const startWidth = width;

			const handleMouseMove = (moveEvent: MouseEvent) => {
				const delta = startX - moveEvent.clientX;
				const newWidth = Math.min(
					MAX_WIDTH,
					Math.max(MIN_WIDTH, startWidth + delta),
				);
				setWidth(newWidth);
			};

			const handleMouseUp = () => {
				setDragging(false);
				window.removeEventListener("mousemove", handleMouseMove);
				window.removeEventListener("mouseup", handleMouseUp);
			};

			window.addEventListener("mousemove", handleMouseMove);
			window.addEventListener("mouseup", handleMouseUp);
		},
		[width],
	);

	const pdfPageWidth = width - 48;

	const customTextRenderer = useMemo(() => {
		if (!highlightClause) return undefined;
		return ({ str }: { str: string }) => {
			// Highlight text containing the clause reference (e.g., "3.2.1" or "Section 8")
			const searchTerms = [
				highlightClause,
				`Section ${highlightClause}`,
				`Clause ${highlightClause}`,
				highlightClause.split("(")[0], // base clause without sub-ref
			].filter(Boolean);

			for (const term of searchTerms) {
				if (str.includes(term)) {
					return str.replace(
						term,
						`<mark style="background-color: #fef08a; padding: 2px 0;">${term}</mark>`,
					);
				}
			}
			return str;
		};
	}, [highlightClause]);

	if (documents.length === 0) {
		return (
			<div
				style={{ width }}
				className="flex h-full flex-shrink-0 flex-col items-center justify-center border-l border-neutral-200 bg-neutral-50"
			>
				<FileText className="mb-3 h-10 w-10 text-neutral-300" />
				<p className="text-sm text-neutral-400">No documents uploaded</p>
			</div>
		);
	}

	const pdfUrl = activeDocument ? getDocumentUrl(activeDocument.id) : null;

	return (
		<div
			ref={containerRef}
			style={{ width }}
			className="relative flex h-full flex-shrink-0 flex-col border-l border-neutral-200 bg-white"
		>
			{/* Resize handle */}
			<div
				className={`absolute top-0 left-0 z-10 h-full w-1.5 cursor-col-resize transition-colors hover:bg-neutral-300 ${
					dragging ? "bg-neutral-400" : ""
				}`}
				onMouseDown={handleMouseDown}
			/>

			{/* Document tabs */}
			<DocumentTabs
				documents={documents}
				activeDocumentId={activeDocumentId}
				onSelect={onDocumentSelect}
			/>

			{/* Citation navigation indicator */}
			{citationActive && !highlightClause && (
				<div className="mx-4 mt-2 rounded-md bg-yellow-50 border border-yellow-200 px-3 py-1.5 text-xs text-yellow-700 flex items-center gap-1.5">
					<span className="inline-block h-2 w-2 rounded-full bg-yellow-400" />
					Referenced page
				</div>
			)}
			{citationActive && highlightClause && (
				<div className="mx-4 mt-2 rounded-md bg-emerald-50 border border-emerald-200 px-3 py-1.5 text-xs text-emerald-700 flex items-center gap-1.5">
					<span className="inline-block h-2 w-2 rounded-full bg-emerald-400" />
					Highlighting: Section {highlightClause}
				</div>
			)}

			{/* PDF content */}
			<div className="flex-1 overflow-y-auto p-4">
				{pdfError && (
					<div className="rounded-lg bg-red-50 p-3 text-sm text-red-600">
						{pdfError}
					</div>
				)}

				{pdfUrl && (
					<PDFDocument
						file={pdfUrl}
						onLoadSuccess={({ numPages: pages }) => {
							setNumPages(pages);
							setPdfLoading(false);
							setPdfError(null);
						}}
						onLoadError={(error) => {
							setPdfError(`Failed to load PDF: ${error.message}`);
							setPdfLoading(false);
						}}
						loading={
							<div className="flex items-center justify-center py-12">
								<Loader2 className="h-6 w-6 animate-spin text-neutral-400" />
							</div>
						}
					>
						{!pdfLoading && !pdfError && (
							<div
								className={
									citationActive && !highlightClause
										? "rounded-sm ring-2 ring-yellow-300 ring-offset-2"
										: ""
								}
							>
								<Page
									pageNumber={activePage}
									width={pdfPageWidth}
									customTextRenderer={customTextRenderer}
									loading={
										<div className="flex items-center justify-center py-12">
											<Loader2 className="h-5 w-5 animate-spin text-neutral-300" />
										</div>
									}
								/>
							</div>
						)}
					</PDFDocument>
				)}
			</div>

			{/* Page navigation */}
			{numPages > 0 && (
				<div className="flex items-center justify-center gap-3 border-t border-neutral-100 px-4 py-2.5">
					<Button
						variant="ghost"
						size="icon"
						className="h-7 w-7"
						disabled={activePage <= 1}
						onClick={() => onPageChange(Math.max(1, activePage - 1))}
					>
						<ChevronLeft className="h-4 w-4" />
					</Button>
					<span className="text-xs text-neutral-500">
						Page {activePage} of {numPages}
					</span>
					<Button
						variant="ghost"
						size="icon"
						className="h-7 w-7"
						disabled={activePage >= numPages}
						onClick={() => onPageChange(Math.min(numPages, activePage + 1))}
					>
						<ChevronRight className="h-4 w-4" />
					</Button>
				</div>
			)}
		</div>
	);
}
