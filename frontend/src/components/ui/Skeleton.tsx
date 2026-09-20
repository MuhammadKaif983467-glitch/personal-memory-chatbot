type Props = {
  width?: string | number
  height?: string | number
  className?: string
  variant?: 'text' | 'circle' | 'rect'
}

const VARIANT_CLASS: Record<string, string> = {
  text: 'skeleton-text',
  circle: 'skeleton-circle',
  rect: 'skeleton-bubble',
}

export function Skeleton({ width, height, className = '', variant = 'text' }: Props) {
  const style: Record<string, string | number> = {}
  if (width != null) style.width = typeof width === 'number' ? `${width}px` : width
  if (height != null) style.height = typeof height === 'number' ? `${height}px` : height

  if (variant === 'circle') {
    style.borderRadius = '50%'
  }

  return (
    <div
      className={`skeleton ${VARIANT_CLASS[variant]} ${className}`}
      style={style}
    />
  )
}
