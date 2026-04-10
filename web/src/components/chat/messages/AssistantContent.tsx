import { useMemo } from 'react';
import { extractSuggestionOptions, type SuggestionOption } from '../suggestionUtils';
import MarkdownMessage from './MarkdownMessage';
import SuggestionCards from './SuggestionCards';
import StoreOrderMessage from './StoreOrderMessage';
import { parseStoreOrderMessage } from './storeOrderMessageParser';

export default function AssistantMessageContent({
  content,
  onApplyOption,
  applyDisabled,
}: {
  content: string;
  onApplyOption?: (option: SuggestionOption, index: number) => void;
  applyDisabled?: boolean;
}) {
  const { markdownContent, options } = useMemo(() => extractSuggestionOptions(content), [content]);
  const storeOrderMessage = useMemo(
    () => (markdownContent ? parseStoreOrderMessage(markdownContent) : null),
    [markdownContent],
  );

  return (
    <div className="space-y-4">
      {storeOrderMessage ? (
        <StoreOrderMessage data={storeOrderMessage} />
      ) : markdownContent ? (
        <MarkdownMessage content={markdownContent} />
      ) : null}
      {options.length > 0 && onApplyOption ? (
        <SuggestionCards options={options} onApplyOption={onApplyOption} disabled={applyDisabled} />
      ) : null}
    </div>
  );
}
