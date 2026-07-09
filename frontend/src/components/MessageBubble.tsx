import { motion } from "framer-motion";
import { Bot } from "lucide-react";
import { Streamdown } from "streamdown";
import "streamdown/styles.css";
import type { Message } from "../types";
import { CitationBadge } from "./CitationBadge";
import { ReportView } from "./ReportView";
import { splitContentWithCitations } from "../lib/citations";

interface MessageBubbleProps {
	message: Message;
	onCitationClick: (documentId: string, pageNumber: number, clause?: string | null) => void;
}

export function MessageBubble({ message, onCitationClick }: MessageBubbleProps) {
	if (message.role === "system") {
		return (
			<motion.div
				initial={{ opacity: 0 }}
				animate={{ opacity: 1 }}
				transition={{ duration: 0.2 }}
				className="flex justify-center py-2"
			>
				<p className="text-xs text-neutral-400">{message.content}</p>
			</motion.div>
		);
	}

	if (message.role === "user") {
		return (
			<motion.div
				initial={{ opacity: 0, y: 8 }}
				animate={{ opacity: 1, y: 0 }}
				transition={{ duration: 0.2 }}
				className="flex justify-end py-1.5"
			>
				<div className="max-w-[75%] rounded-2xl rounded-br-md bg-neutral-100 px-4 py-2.5">
					<p className="whitespace-pre-wrap text-sm text-neutral-800">
						{message.content}
					</p>
				</div>
			</motion.div>
		);
	}

	// Assistant message — render report or chat based on message_type
	if (message.message_type === "report") {
		return (
			<motion.div
				initial={{ opacity: 0, y: 8 }}
				animate={{ opacity: 1, y: 0 }}
				transition={{ duration: 0.2 }}
				className="flex gap-3 py-1.5"
			>
				<div className="flex h-7 w-7 flex-shrink-0 items-center justify-center rounded-full bg-neutral-900">
					<Bot className="h-4 w-4 text-white" />
				</div>
				<div className="min-w-0 max-w-[85%]">
					<ReportView
						content={message.content}
						citations={message.citations || []}
						sourcesCited={message.sources_cited}
						onCitationClick={onCitationClick}
					/>
				</div>
			</motion.div>
		);
	}

	const segments = splitContentWithCitations(
		message.content,
		message.citations || [],
	);

	const hasCitations = segments.some((s) => s.type === "citation");

	return (
		<motion.div
			initial={{ opacity: 0, y: 8 }}
			animate={{ opacity: 1, y: 0 }}
			transition={{ duration: 0.2 }}
			className="flex gap-3 py-1.5"
		>
			<div className="flex h-7 w-7 flex-shrink-0 items-center justify-center rounded-full bg-neutral-900">
				<Bot className="h-4 w-4 text-white" />
			</div>
			<div className="min-w-0 max-w-[80%]">
				{hasCitations ? (
					<div className="prose prose-sm">
						{segments.map((segment, i) => {
							if (segment.type === "text" && segment.text) {
								return (
									<Streamdown key={`text-${i}`}>
										{segment.text}
									</Streamdown>
								);
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
					</div>
				) : (
					<div className="prose">
						<Streamdown>{message.content}</Streamdown>
					</div>
				)}
				{message.sources_cited > 0 && (
					<p className="mt-1.5 text-xs text-neutral-400">
						{message.sources_cited} source
						{message.sources_cited !== 1 ? "s" : ""} cited
					</p>
				)}
				{message.confidence === "low" && (
					<p className="mt-1.5 text-xs text-yellow-600">
						&#x26A0; Low confidence &mdash; answer may be incomplete
					</p>
				)}
			</div>
		</motion.div>
	);
}

interface StreamingBubbleProps {
	content: string;
}

export function StreamingBubble({ content }: StreamingBubbleProps) {
	return (
		<div className="flex gap-3 py-1.5">
			<div className="flex h-7 w-7 flex-shrink-0 items-center justify-center rounded-full bg-neutral-900">
				<Bot className="h-4 w-4 text-white" />
			</div>
			<div className="min-w-0 max-w-[80%]">
				{content ? (
					<>
						<div className="prose">
							<Streamdown mode="streaming">{content}</Streamdown>
						</div>
						<span className="inline-block h-4 w-0.5 animate-pulse bg-neutral-400" />
					</>
				) : (
					<div className="flex items-center gap-1 py-2">
						<span className="h-1.5 w-1.5 animate-pulse rounded-full bg-neutral-400" />
						<span
							className="h-1.5 w-1.5 animate-pulse rounded-full bg-neutral-400"
							style={{ animationDelay: "0.15s" }}
						/>
						<span
							className="h-1.5 w-1.5 animate-pulse rounded-full bg-neutral-400"
							style={{ animationDelay: "0.3s" }}
						/>
					</div>
				)}
			</div>
		</div>
	);
}
