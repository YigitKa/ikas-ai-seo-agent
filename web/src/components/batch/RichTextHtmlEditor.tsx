import { useEffect, useRef } from 'react';
import Quill from 'quill';
import 'quill/dist/quill.snow.css';

const TOOLBAR_OPTIONS = [
  [{ header: [2, 3, 4, false] }, { size: ['small', false, 'large', 'huge'] }],
  ['bold', 'italic', 'underline', 'strike'],
  [{ color: [] }, { background: [] }, { script: 'super' }, { script: 'sub' }],
  [{ list: 'ordered' }, { list: 'bullet' }, { indent: '-1' }, { indent: '+1' }],
  [{ align: [] }, { direction: 'rtl' }],
  ['blockquote', 'code-block', 'link', 'image'],
  ['clean'],
];

function escapeHtml(value: string): string {
  return value
    .replaceAll('&', '&amp;')
    .replaceAll('<', '&lt;')
    .replaceAll('>', '&gt;')
    .replaceAll('"', '&quot;')
    .replaceAll("'", '&#39;');
}

function toEditorHtml(value: string): string {
  const normalized = value.trim();
  if (!normalized) return '<p><br></p>';
  if (/<[^>]+>/.test(normalized)) return normalized;
  return `<p>${escapeHtml(normalized).replaceAll('\n', '<br />')}</p>`;
}

function normalizeHtml(value: string): string {
  return value
    .replace(/^<p><br><\/p>$/i, '')
    .replace(/^<p><br \/><\/p>$/i, '')
    .trim();
}

export default function RichTextHtmlEditor({
  value,
  onChange,
  disabled,
}: {
  value: string;
  onChange: (next: string) => void;
  disabled: boolean;
}) {
  const toolbarRef = useRef<HTMLDivElement | null>(null);
  const editorRef = useRef<HTMLDivElement | null>(null);
  const quillRef = useRef<Quill | null>(null);
  const onChangeRef = useRef(onChange);
  const initialValueRef = useRef(value);
  const initialDisabledRef = useRef(disabled);

  useEffect(() => {
    onChangeRef.current = onChange;
  }, [onChange]);

  useEffect(() => {
    const toolbarElement = toolbarRef.current;
    const editorElement = editorRef.current;
    if (!toolbarElement || !editorElement) return;

    editorElement.innerHTML = toEditorHtml(initialValueRef.current);

    const quill = new Quill(editorElement, {
      theme: 'snow',
      readOnly: initialDisabledRef.current,
      placeholder: 'İçeriği zengin metin olarak düzenleyin',
      modules: {
        toolbar: toolbarElement,
        history: {
          delay: 300,
          maxStack: 100,
          userOnly: true,
        },
      },
    });

    const handleTextChange = () => {
      const nextHtml = normalizeHtml(quill.getSemanticHTML());
      onChangeRef.current(nextHtml);
    };

    quill.on('text-change', handleTextChange);
    quillRef.current = quill;

    return () => {
      quill.off('text-change', handleTextChange);
      quillRef.current = null;
      editorElement.innerHTML = '';
    };
  }, []);

  useEffect(() => {
    const quill = quillRef.current;
    if (!quill) return;
    quill.enable(!disabled);
  }, [disabled]);

  useEffect(() => {
    const quill = quillRef.current;
    if (!quill) return;

    const currentHtml = normalizeHtml(quill.getSemanticHTML());
    const nextHtml = normalizeHtml(value);
    if (currentHtml === nextHtml) return;

    const delta = quill.clipboard.convert({
      html: toEditorHtml(value),
      text: '',
    });
    quill.setContents(delta, 'silent');
  }, [value]);

  return (
    <div className="quill-standard-editor space-y-0">
      <div ref={toolbarRef}>
        {TOOLBAR_OPTIONS.map((group, groupIndex) => (
          <span key={`group-${groupIndex}`} className="ql-formats">
            {group.map((item, itemIndex) => {
              if (typeof item === 'string') {
                return <button key={`${item}-${itemIndex}`} type="button" className={`ql-${item}`} />;
              }

              const [format, rawValue] = Object.entries(item)[0];
              if (Array.isArray(rawValue)) {
                return (
                  <select key={`${format}-${itemIndex}`} className={`ql-${format}`} defaultValue="">
                    {rawValue.map((optionValue, optionIndex) => (
                      <option
                        key={`${format}-${String(optionValue)}-${optionIndex}`}
                        value={optionValue === false ? '' : String(optionValue)}
                      />
                    ))}
                  </select>
                );
              }

              return (
                <button
                  key={`${format}-${String(rawValue)}-${itemIndex}`}
                  type="button"
                  className={`ql-${format}`}
                  value={String(rawValue)}
                />
              );
            })}
          </span>
        ))}
      </div>

      <div ref={editorRef} />
    </div>
  );
}
