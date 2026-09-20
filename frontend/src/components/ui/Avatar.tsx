type Props = {
  name: string
  size?: 'sm' | 'md' | 'lg'
  className?: string
}

const SIZE_MAP: Record<string, string> = {
  sm: '28px',
  md: '36px',
  lg: '56px',
}

const FONT_SIZE_MAP: Record<string, string> = {
  sm: '0.65rem',
  md: '0.85rem',
  lg: '1.2rem',
}

function initial(name: string): string {
  return name.charAt(0).toUpperCase()
}

export function Avatar({ name, size = 'md', className = '' }: Props) {
  const dim = SIZE_MAP[size]
  const fontSize = FONT_SIZE_MAP[size]

  return (
    <div
      className={`avatar avatar-accent ${className}`}
      style={{ width: dim, height: dim, fontSize }}
      title={name}
    >
      {initial(name)}
    </div>
  )
}
