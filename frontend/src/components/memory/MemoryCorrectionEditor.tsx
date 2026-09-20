import MemoryEditor from './MemoryEditor'

interface Props {
  content: string
  onChange: (value: string) => void
  onSave: () => void
  onCancel: () => void
}

export default function MemoryCorrectionEditor({ content, onChange, onSave, onCancel }: Props) {
  return (
    <MemoryEditor
      content={content}
      onChange={onChange}
      onSave={onSave}
      onCancel={onCancel}
      placeholder="Corrected content..."
    />
  )
}
