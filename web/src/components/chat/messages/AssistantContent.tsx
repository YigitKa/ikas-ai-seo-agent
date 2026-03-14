import { extractSuggestionOptions, type SuggestionOption } from '../suggestionUtils';
import MarkdownMessage from './MarkdownMessage';
import SuggestionCards from './SuggestionCards';

export default function AssistantMessageContent({
  content,
  onApplyOption,
  applyDisabled,
}: {
  content: string;
  onApplyOption?: (option: SuggestionOption, index: number) => void;
  applyDisabled?: boolean;
}) {
  const { markdownContent, options } = extractSuggestionOptions(content);

  return (
    <div className="space-y-4">
      {markdownContent ? <MarkdownMessage content={markdownContent} /> : null}
      {options.length > 0 && onApplyOption ? (
        <SuggestionCards options={options} onApplyOption={onApplyOption} disabled={applyDisabled} />
      ) : null}
    </div>
  );
}
