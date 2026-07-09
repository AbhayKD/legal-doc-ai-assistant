import { useCallback, useState } from "react";
import { ChatSidebar } from "./components/ChatSidebar";
import { ChatWindow } from "./components/ChatWindow";
import { DocumentViewer } from "./components/DocumentViewer";
import { TooltipProvider } from "./components/ui/tooltip";
import { useConversations } from "./hooks/use-conversations";
import { useDocuments } from "./hooks/use-documents";
import { useMessages } from "./hooks/use-messages";

export default function App() {
	const {
		conversations,
		selectedId,
		loading: conversationsLoading,
		create,
		select,
		remove,
		refresh: refreshConversations,
	} = useConversations();

	const {
		messages,
		loading: messagesLoading,
		error: messagesError,
		streaming,
		streamingContent,
		send,
		sendReport,
	} = useMessages(selectedId);

	const {
		documents,
		activeDocumentId,
		activePage,
		upload,
		navigateTo,
		setPage,
		refresh: refreshDocuments,
	} = useDocuments(selectedId);

	const [highlightClause, setHighlightClause] = useState<string | null>(null);
	const [citationActive, setCitationActive] = useState(false);

	const handleSend = useCallback(
		async (content: string) => {
			await send(content);
			refreshConversations();
		},
		[send, refreshConversations],
	);

	const handleGenerateReport = useCallback(async () => {
		await sendReport();
		refreshConversations();
	}, [sendReport, refreshConversations]);

	const handleUpload = useCallback(
		async (file: File) => {
			const doc = await upload(file);
			if (doc) {
				refreshDocuments();
				refreshConversations();
			}
		},
		[upload, refreshDocuments, refreshConversations],
	);

	const handleCreate = useCallback(async () => {
		await create();
	}, [create]);

	const handleCitationClick = useCallback(
		(documentId: string, pageNumber: number, clause?: string | null) => {
			navigateTo(documentId, pageNumber);
			setHighlightClause(clause ?? null);
			setCitationActive(true);
		},
		[navigateTo],
	);

	const handleDocumentSelect = useCallback(
		(docId: string) => {
			navigateTo(docId, 1);
			setHighlightClause(null);
			setCitationActive(false);
		},
		[navigateTo],
	);

	return (
		<TooltipProvider delayDuration={200}>
			<div className="flex h-screen bg-neutral-50">
				<ChatSidebar
					conversations={conversations}
					selectedId={selectedId}
					loading={conversationsLoading}
					onSelect={select}
					onCreate={handleCreate}
					onDelete={remove}
				/>

				<ChatWindow
					messages={messages}
					loading={messagesLoading}
					error={messagesError}
					streaming={streaming}
					streamingContent={streamingContent}
					hasDocuments={documents.length > 0}
					conversationId={selectedId}
					onSend={handleSend}
					onUpload={handleUpload}
					onGenerateReport={handleGenerateReport}
					onCitationClick={handleCitationClick}
				/>

				<DocumentViewer
					documents={documents}
					activeDocumentId={activeDocumentId}
					activePage={activePage}
					highlightClause={highlightClause}
					citationActive={citationActive}
					onDocumentSelect={handleDocumentSelect}
					onPageChange={(page) => {
						setPage(page);
						setCitationActive(false);
						setHighlightClause(null);
					}}
				/>
			</div>
		</TooltipProvider>
	);
}
