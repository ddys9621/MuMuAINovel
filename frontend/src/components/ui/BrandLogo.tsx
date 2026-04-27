import { cn } from '@/lib/utils'

interface BrandLogoProps {
  size?: 'sm' | 'md' | 'lg'
  className?: string
  textClassName?: string
}

const SIZE_MAP = {
  sm: 'h-9 w-9 rounded-2xl text-sm',
  md: 'h-10 w-10 rounded-2xl text-base',
  lg: 'h-12 w-12 rounded-[20px] text-lg',
} as const

export function BrandLogo({ size = 'md', className, textClassName }: BrandLogoProps) {
  return (
    <span
      className={cn(
        'relative inline-flex items-center justify-center overflow-hidden bg-gradient-to-br from-[#ff6d4b] via-[#ff8f63] to-[#ffca86] font-black tracking-[-0.08em] text-white shadow-lg shadow-brand/25',
        SIZE_MAP[size],
        className,
      )}
      aria-hidden="true"
    >
      <span className="absolute inset-0 bg-[radial-gradient(circle_at_top_left,rgba(255,255,255,0.34),transparent_34%)]" />
      <span className={cn('relative translate-x-[-0.02em]', textClassName)}>HH</span>
    </span>
  )
}
