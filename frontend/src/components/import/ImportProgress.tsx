type Stage = 'idle' | 'validating' | 'uploading' | 'analyzing' | 'done'

const STAGE_LABEL: Record<Stage, string> = {
  idle: 'Ready', validating: 'Validating\u2026', uploading: 'Uploading\u2026', analyzing: 'Analyzing\u2026', done: 'Done',
}

const STAGE_PCT: Record<Stage, number> = { idle: 0, validating: 30, uploading: 60, analyzing: 85, done: 100 }

type Props = { stage: Stage }

export function ImportProgress({ stage }: Props) {
  return (
    <div className="progress" role="status" aria-live="polite">
      <div className="progress-bar" style={{ width: `${STAGE_PCT[stage]}%` }} />
      <span>{STAGE_LABEL[stage]}</span>
    </div>
  )
}
